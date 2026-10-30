"""Independent G07a runner/CLI/JSONL integration with no real wait or IO services."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import socket
import ssl
import subprocess
import sys
from urllib.error import HTTPError, URLError

import pytest
import requests
from sqlalchemy.exc import OperationalError, ProgrammingError, TimeoutError as PoolTimeout

from invest_bot.config.settings import AppSettings
from invest_bot.dashboard.streamlit_overview import schedule_collection_failed
from invest_bot.jobs import scheduled_collection as job


REAL_RUNNER = job.ScheduledCollectionRunner
OK = {"success_count": 2, "failed_count": 0, "symbols": ["005930", "000660"]}


@pytest.fixture(autouse=True)
def forbid_implicit_settings_db_and_real_sleep(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("G07a independent fixture attempted real settings/DB/sleep")
    monkeypatch.setattr(AppSettings, "from_file", forbidden)
    monkeypatch.setattr(job.time, "sleep", forbidden)
    import invest_bot.db.engine as engine
    monkeypatch.setattr(engine, "build_engine", forbidden)
    monkeypatch.setattr(engine, "create_engine", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)


class Cycle:
    def __init__(self, tmp_path, outcomes, *, startup=True, phase="collector"):
        self.config_path = tmp_path / "schedule.yaml"
        self.log_path = tmp_path / "runtime" / "cycle.jsonl"
        self.config_path.write_text(
            "symbols: ['005930', '000660']\ndays: 37\ninterval_minutes: 7\n"
            f"run_on_startup: {str(startup).lower()}\nlog_path: {self.log_path.as_posix()}\n", encoding="utf-8")
        self.schedule = job.CollectionScheduleConfig.from_file(self.config_path)
        self.clock = datetime(2026, 10, 29, 9, 12, 3)
        self.initial = self.clock
        self.outcomes = outcomes
        self.phase = phase
        self.attempt = -1
        self.trace = []
        self.waits = []
        self.waiting_states = []
        self.clock_reads = 0
        self.runner = REAL_RUNNER(self.schedule, collector_fn=self.collect,
                                  before_run_fn=self.before, now_fn=self.now, sleep_fn=self.sleep)

    def now(self):
        self.clock_reads += 1
        return self.clock

    def before(self):
        self.attempt += 1
        self.trace.append(("hook", self.attempt, self.clock))
        self.clock += timedelta(seconds=5)
        outcome = self.outcomes[self.attempt]
        if self.phase == "hook" and isinstance(outcome, BaseException):
            raise outcome

    def collect(self, symbols, days):
        assert symbols == ["005930", "000660"] and days == 37
        self.trace.append(("collector", self.attempt, self.clock))
        self.clock += timedelta(seconds=17)
        outcome = self.outcomes[self.attempt]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def sleep(self, seconds):
        assert seconds == 420
        self.trace.append(("sleep", seconds, self.clock))
        self.waits.append(seconds)
        state = job.load_schedule_status(self.config_path)
        assert state.last_event == "collection_waiting"
        assert datetime.fromisoformat(state.next_run_at) == self.clock + timedelta(seconds=420)
        self.waiting_states.append(state)
        self.clock += timedelta(seconds=seconds)

    def entries(self):
        return [json.loads(line) for line in self.log_path.read_text().splitlines()] if self.log_path.exists() else []

    def events(self):
        return [entry["event"] for entry in self.entries()]

    def status(self):
        return job.load_schedule_status(self.config_path)


def connect_real_main(monkeypatch, cycle, *arguments):
    instances = []
    def factory(schedule, before_run_fn):
        assert schedule == cycle.schedule
        assert before_run_fn == cycle.before
        runner = REAL_RUNNER(schedule, collector_fn=cycle.collect, before_run_fn=before_run_fn,
                             sleep_fn=cycle.sleep, now_fn=cycle.now)
        instances.append(runner)
        return runner
    monkeypatch.setattr(job, "sync_stock_master", cycle.before)
    monkeypatch.setattr(job, "ScheduledCollectionRunner", factory)
    monkeypatch.setattr(sys, "argv", ["scheduled_collection", "--config", str(cycle.config_path), *arguments])
    return instances


@pytest.mark.parametrize("startup", [True, False])
@pytest.mark.parametrize("phase", ["hook", "collector"])
def test_real_main_startup_failure_wait_success_and_jsonl_state(monkeypatch, tmp_path, startup, phase):
    error = RuntimeError("independent startup failure")
    cycle = Cycle(tmp_path, [error, OK], startup=startup, phase=phase)
    instances = connect_real_main(monkeypatch, cycle, "--max-runs", "2")
    job.main()
    assert len(instances) == 1  # one real runner, no re-created process/runner per failure
    expected = ["collection_started", "collection_failed", "collection_waiting", "collection_started", "collection_finished"]
    assert cycle.events() == (["collection_waiting"] if not startup else []) + expected
    assert cycle.waits == ([420, 420] if not startup else [420])
    assert len([step for step in cycle.trace if step[0] == "hook"]) == 2
    assert len([step for step in cycle.trace if step[0] == "collector"]) == (1 if phase == "hook" else 2)
    state = cycle.status()
    assert state.total_logged_runs == 1  # completion count, not attempted cycles
    assert state.last_error == str(error)
    assert state.last_failed_at and state.last_finished_at and state.last_success_count == 2
    assert not schedule_collection_failed(state)
    recovery_wait = next(entry for entry in cycle.entries()[1:] if entry["event"] == "collection_waiting") if startup else cycle.entries()[3]
    assert datetime.fromisoformat(recovery_wait["next_run_at"]) == datetime.fromisoformat(state.last_failed_at) + timedelta(seconds=420)


def test_later_cycle_failure_waits_from_failure_end_not_previous_start(tmp_path):
    cycle = Cycle(tmp_path, [OK, requests.Timeout("later timeout"), OK])
    assert cycle.runner.run_forever(max_runs=3) == 3
    assert cycle.waits == [420, 420]
    entries = cycle.entries()
    assert cycle.events() == ["collection_started", "collection_finished", "collection_waiting",
                              "collection_started", "collection_failed", "collection_waiting",
                              "collection_started", "collection_finished"]
    assert datetime.fromisoformat(entries[5]["next_run_at"]) == datetime.fromisoformat(entries[4]["failed_at"]) + timedelta(seconds=420)
    assert cycle.waiting_states[1].total_logged_runs == 1
    assert schedule_collection_failed(cycle.waiting_states[1])
    assert cycle.status().total_logged_runs == 2 and not schedule_collection_failed(cycle.status())


@pytest.mark.parametrize("startup", [True, False])
@pytest.mark.parametrize("limit", [0, 1, 3])
def test_attempt_cap_counts_repeated_failures_and_never_waits_after_last_attempt(tmp_path, startup, limit):
    cycle = Cycle(tmp_path, [RuntimeError(f"failed attempt {index}") for index in range(limit)], startup=startup)
    assert cycle.runner.run_forever(max_runs=limit) == limit
    assert cycle.attempt + 1 == limit
    assert cycle.waits == [420] * (max(0, limit - 1) if startup else limit)
    assert cycle.status().total_logged_runs == 0
    if limit:
        assert cycle.events()[-1] == "collection_failed"
        assert cycle.status().last_error == f"failed attempt {limit - 1}"
    else:
        assert not cycle.log_path.exists() and cycle.clock_reads == 0 and cycle.trace == []


@pytest.mark.parametrize("failed_count", [1, 2])
def test_partial_or_full_failed_count_dict_finishes_without_immediate_duplicate_collection(tmp_path, failed_count):
    partial = {"success_count": 2 - failed_count, "failed_count": failed_count, "symbols": []}
    cycle = Cycle(tmp_path, [partial, OK])
    assert cycle.runner.run_forever(max_runs=2) == 2
    assert cycle.events() == ["collection_started", "collection_finished", "collection_waiting", "collection_started", "collection_finished"]
    assert cycle.waits == [420]
    first = cycle.waiting_states[0]
    assert first.total_logged_runs == 1 and first.last_failed_count == failed_count
    assert cycle.status().total_logged_runs == 2
    assert len([step for step in cycle.trace if step[0] == "collector"]) == 2


class DifferentRuntimeError(RuntimeError):
    pass


def exception_cases():
    cases = []
    for status in [408, 429, 503, 401]:
        retry = status != 401
        cases.append(pytest.param(HTTPError("https://example.invalid", status, "fake", {}, None), retry, id=f"urllib-{status}"))
        response = requests.Response()
        response.status_code = status
        cases.append(pytest.param(requests.HTTPError("fake HTTP", response=response), retry, id=f"requests-{status}"))
    response = requests.Response()
    response.status_code = 599
    cases.extend([
        pytest.param(HTTPError("https://example.invalid", 499, "fake", {}, None), False, id="urllib-499"),
        pytest.param(requests.HTTPError("fake 599", response=response), True, id="requests-599"),
        pytest.param(requests.HTTPError("no response"), False, id="requests-no-response"),
    ])
    for name, reason, retry in [
        ("dns", socket.gaierror(socket.EAI_AGAIN, "synthetic DNS"), True),
        ("connection", ConnectionRefusedError("synthetic refused"), True),
        ("ssl", ssl.SSLError("synthetic TLS"), False),
        ("certificate", ssl.SSLCertVerificationError("synthetic certificate"), False),
        ("permission", PermissionError("synthetic local permission"), False),
        ("file", FileNotFoundError("synthetic local file"), False),
        ("input", ValueError("synthetic credentials/input"), False),
        ("type", TypeError("synthetic reason type"), False),
    ]:
        cases.append(pytest.param(URLError(reason), retry, id=f"url-reason-{name}"))
    for name, error, retry in [
        ("requests-ssl", requests.exceptions.SSLError("synthetic SSL"), False),
        ("requests-timeout", requests.Timeout("synthetic timeout"), True),
        ("requests-connect", requests.ConnectionError("synthetic connection"), True),
        ("pool-timeout", PoolTimeout("synthetic pool timeout"), True),
        ("db-invalidated", OperationalError(None, None, ConnectionResetError("synthetic disconnect"), connection_invalidated=True), True),
        ("db-auth", OperationalError(None, None, PermissionError("synthetic authentication")), False),
        ("db-unknown", OperationalError(None, None, Exception("synthetic unclassified DB")), False),
        ("db-programming", ProgrammingError(None, None, Exception("synthetic SQL"), connection_invalidated=True), False),
        ("exact-runtime", RuntimeError("synthetic job failure"), True),
        ("runtime-subclass", DifferentRuntimeError("synthetic subclass"), False),
        ("unimplemented", NotImplementedError("synthetic implementation bug"), False),
        ("recursion", RecursionError("synthetic recursion bug"), False),
        ("builtin-timeout", TimeoutError("synthetic timeout"), True),
        ("builtin-connect", ConnectionError("synthetic connection"), True),
        ("input", ValueError("synthetic input"), False),
        ("local-os", OSError("synthetic local IO"), False),
    ]:
        cases.append(pytest.param(error, retry, id=name))
    return cases


@pytest.mark.parametrize("error,retry", exception_cases())
def test_actual_runner_exception_objects_produce_bounded_wait_or_original_exception(tmp_path, error, retry):
    cycle = Cycle(tmp_path, [error, OK])
    if retry:
        assert cycle.runner.run_forever(max_runs=2) == 2
        assert cycle.events() == ["collection_started", "collection_failed", "collection_waiting", "collection_started", "collection_finished"]
        assert cycle.waits == [420] and cycle.status().total_logged_runs == 1
    else:
        with pytest.raises(type(error)) as caught:
            cycle.runner.run_forever(max_runs=2)
        assert caught.value is error
        assert cycle.events() == ["collection_started", "collection_failed"]
        assert cycle.waits == [] and cycle.status().total_logged_runs == 0
    assert cycle.entries()[1]["error_type"] == type(error).__name__


@pytest.mark.parametrize("location", ["sleep", "clock", "failed-log"])
@pytest.mark.parametrize("error_type", [RuntimeError, OSError, KeyboardInterrupt, SystemExit])
def test_infrastructure_runtime_os_and_control_errors_escape_exactly(monkeypatch, tmp_path, location, error_type):
    cycle = Cycle(tmp_path, [RuntimeError("retryable callback failure"), OK])
    error = error_type("independent infrastructure error")
    def fail(*_args, **_kwargs):
        raise error
    if location == "sleep":
        cycle.runner.sleep_fn = fail
    elif location == "clock":
        cycle.runner.now_fn = fail
    else:
        append = REAL_RUNNER._append_log
        def record(runner, payload):
            if payload["event"] == "collection_failed":
                raise error
            return append(runner, payload)
        monkeypatch.setattr(REAL_RUNNER, "_append_log", record)
    with pytest.raises(error_type) as caught:
        cycle.runner.run_forever(max_runs=2)
    assert caught.value is error
    assert cycle.attempt <= 0  # no second callback cycle


@pytest.mark.parametrize("error", [RuntimeError("once exact error"), KeyboardInterrupt(), SystemExit(19)])
def test_actual_main_once_preserves_exception_identity_and_never_waits(monkeypatch, tmp_path, error):
    cycle = Cycle(tmp_path, [error])
    connect_real_main(monkeypatch, cycle, "--once")
    with pytest.raises(type(error)) as caught:
        job.main()
    assert caught.value is error and cycle.waits == []
    assert cycle.events() == (["collection_started", "collection_failed"] if isinstance(error, Exception) else ["collection_started"])


def test_actual_once_script_exits_nonzero_with_synthetic_callbacks_only(tmp_path):
    cycle = Cycle(tmp_path, [])
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts/run_scheduled_collection.py"
    code = '''
import socket, sys, runpy
from datetime import datetime
def forbidden(*args, **kwargs):
    raise AssertionError("QA07 forbidden network/sleep")
socket.socket.connect = forbidden
from invest_bot.jobs import scheduled_collection as job
real = job.ScheduledCollectionRunner
def collect(**kwargs):
    raise RuntimeError("QA07_ONCE_ORIGINAL_FAILURE")
def factory(schedule, before_run_fn):
    return real(schedule, collector_fn=collect, before_run_fn=lambda: None,
                sleep_fn=forbidden, now_fn=lambda: datetime(2026, 10, 29, 9, 12, 3))
job.ScheduledCollectionRunner = factory
sys.argv = [sys.argv[2], "--config", sys.argv[1], "--once"]
runpy.run_path(sys.argv[0], run_name="__main__")
'''
    environment = dict(os.environ, PYTHONPATH=str(root / "src"), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "-B", "-c", code, str(cycle.config_path), str(script)],
                            cwd=root, env=environment, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert "RuntimeError: QA07_ONCE_ORIGINAL_FAILURE" in result.stderr
    assert "QA07 forbidden" not in result.stderr
    assert cycle.events() == ["collection_started", "collection_failed"]


@pytest.mark.parametrize("limit", ["0", "-4"])
def test_actual_main_zero_or_negative_cli_cap_has_no_callbacks_clock_log_or_sleep(monkeypatch, tmp_path, limit):
    cycle = Cycle(tmp_path, [])
    connect_real_main(monkeypatch, cycle, "--max-runs", limit)
    job.main()
    assert cycle.trace == [] and cycle.clock_reads == 0 and not cycle.log_path.exists()


@pytest.mark.parametrize("valid", [True, False])
def test_actual_main_validation_only_has_no_runtime_or_log_side_effects(monkeypatch, tmp_path, valid, capsys):
    cycle = Cycle(tmp_path, [])
    if not valid:
        cycle.config_path.write_text("symbols: []\ninterval_minutes: 7\n", encoding="utf-8")
    unexpected = []
    def forbidden(*_args, **_kwargs):
        unexpected.append(True)
        pytest.fail("validation constructed a runner or attempted a runtime hook")
    monkeypatch.setattr(job, "ScheduledCollectionRunner", forbidden)
    monkeypatch.setattr(job, "sync_stock_master", forbidden)
    monkeypatch.setattr(job, "collect_market_data_for_symbols", forbidden)
    monkeypatch.setattr(sys, "argv", ["schedule", "--config", str(cycle.config_path), "--validate-config"])
    if valid:
        job.main()
        assert "configuration is valid" in capsys.readouterr().out
    else:
        with pytest.raises(SystemExit, match="Invalid collection schedule"):
            job.main()
    assert unexpected == [] and not cycle.log_path.parent.exists()
