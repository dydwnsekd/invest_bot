from __future__ import annotations

import json
import os
import socket
import ssl
import subprocess
import sys
from datetime import datetime, timedelta
from urllib.error import HTTPError as UrllibHTTPError, URLError

import pytest
import requests
import yaml
from sqlalchemy.exc import OperationalError, ProgrammingError, TimeoutError as PoolTimeoutError

from invest_bot.jobs import scheduled_collection
from invest_bot.jobs.collect_market_data import DEFAULT_COLLECTION_LOOKBACK_DAYS
from invest_bot.jobs.scheduled_collection import CollectionScheduleConfig, ScheduledCollectionRunner, load_schedule_status
from tests.helpers import make_test_dir


class _UnknownRuntimeError(RuntimeError):
    pass


def _g07_error(kind):
    if kind.startswith("urllib-http-"):
        return UrllibHTTPError("https://example.invalid", int(kind.rsplit("-", 1)[1]), "mock", {}, None)
    if kind.startswith("requests-http-") and kind.rsplit("-", 1)[1].isdigit():
        response = requests.Response()
        response.status_code = int(kind.rsplit("-", 1)[1])
        return requests.HTTPError("mock response", response=response)
    return {
        "runtime": RuntimeError("collector unavailable"),
        "url": URLError("master unavailable"),
        "url-dns": URLError(socket.gaierror(socket.EAI_AGAIN, "mock temporary DNS failure")),
        "url-connection": URLError(ConnectionRefusedError("mock refused connection")),
        "url-permission": URLError(PermissionError("local permission")),
        "url-missing-file": URLError(FileNotFoundError("local file missing")),
        "url-ssl": URLError(ssl.SSLCertVerificationError("mock certificate failure")),
        "request-timeout": requests.Timeout("mock timeout"),
        "request-connection": requests.ConnectionError("mock connection"),
        "request-ssl": requests.exceptions.SSLError("mock certificate failure"),
        "request-http-unknown": requests.HTTPError("no response"),
        "timeout": TimeoutError("mock timeout"),
        "connection": ConnectionError("mock connection"),
        "pool-timeout": PoolTimeoutError("mock pool timeout"),
        "db-disconnected": OperationalError(None, None, Exception("mock disconnect"), connection_invalidated=True),
        "db-unknown": OperationalError(None, None, Exception("mock unknown")),
        "db-programming": ProgrammingError(None, None, Exception("mock SQL"), connection_invalidated=True),
        "value": ValueError("missing credentials"),
        "yaml": yaml.YAMLError("mock bad YAML"),
        "type": TypeError("mock wrong type"),
        "key": KeyError("mock missing key"),
        "attribute": AttributeError("mock missing attribute"),
        "unimplemented": NotImplementedError("mock programming error"),
        "recursion": RecursionError("mock programming error"),
        "assertion": AssertionError("mock invariant"),
        "unknown": Exception("mock unknown error"),
        "unknown-runtime": _UnknownRuntimeError("mock unclassified subclass"),
        "permission": PermissionError("mock log permission"),
        "file": FileNotFoundError("mock file missing"),
        "os": OSError("mock disk failure"),
        "interrupt": KeyboardInterrupt(),
        "exit": SystemExit(9),
    }[kind]


@pytest.fixture
def g07_cycle(tmp_path):
    def build(outcomes, *, startup=True, phase="collector"):
        config = tmp_path / "schedule.yaml"
        config.write_text(
            f"symbols: ['005930']\ninterval_minutes: 5\nrun_on_startup: {str(startup).lower()}\nlog_path: cycle.log\n",
            encoding="utf-8",
        )
        schedule = CollectionScheduleConfig.from_file(config)
        pending = iter(outcomes)
        trace = []
        waits = []
        waiting_states = []
        clock = [datetime(2026, 10, 29, 9)]

        def next_outcome():
            clock[0] += timedelta(seconds=2)
            result = next(pending)
            if isinstance(result, BaseException):
                raise result
            return result

        def before():
            trace.append("sync")
            if phase == "master":
                next_outcome()

        def collect(symbols, days):
            trace.append("collector")
            if phase == "collector":
                return next_outcome()
            return {"success_count": 1, "failed_count": 0}

        def sleep(seconds):
            trace.append("sleep")
            waits.append(seconds)
            waiting_states.append(load_schedule_status(config))
            clock[0] += timedelta(seconds=seconds)

        runner = ScheduledCollectionRunner(
            schedule=schedule, collector_fn=collect, before_run_fn=before,
            now_fn=lambda: clock[0], sleep_fn=sleep,
        )
        return runner, config, trace, waits, waiting_states

    return build


@pytest.mark.parametrize("phase", ["collector", "master"])
@pytest.mark.parametrize("fail_at", [0, 1])
def test_g07_failure_waits_then_recovers_in_same_runner(g07_cycle, phase, fail_at):
    from invest_bot.dashboard.streamlit_overview import schedule_collection_failed

    success = {"success_count": 1, "failed_count": 0}
    outcomes = [success] * fail_at + [RuntimeError("mock unavailable"), success]
    runner, config, trace, waits, waiting_states = g07_cycle(outcomes, phase=phase)

    assert runner.run_forever(max_runs=len(outcomes)) == len(outcomes)

    entries = load_schedule_status(config).recent_entries
    expected_events = ["collection_started", "collection_finished", "collection_waiting"] * fail_at
    expected_events += ["collection_started", "collection_failed", "collection_waiting",
                        "collection_started", "collection_finished"]
    assert [entry["event"] for entry in entries] == expected_events
    assert waits == [300] * (fail_at + 1)
    failed_at = datetime(2026, 10, 29, 9) + timedelta(seconds=2 + 302 * fail_at)
    failed = next(entry for entry in entries if entry["event"] == "collection_failed")
    assert failed["failed_at"] == failed_at.isoformat(timespec="seconds")
    assert entries[-3]["next_run_at"] == (failed_at + timedelta(minutes=5)).isoformat(timespec="seconds")
    assert entries[-2]["started_at"] == entries[-3]["next_run_at"]
    assert waiting_states[-1].last_event == "collection_waiting"
    assert schedule_collection_failed(waiting_states[-1])
    status = load_schedule_status(config)
    assert status.last_error == "mock unavailable"
    assert status.total_logged_runs == fail_at + 1
    assert not schedule_collection_failed(status)
    failed_trace = ["sync"] if phase == "master" else ["sync", "collector"]
    assert trace == (["sync", "collector", "sleep"] * fail_at + failed_trace
                     + ["sleep", "sync", "collector"])


@pytest.mark.parametrize("kind", [
    "runtime", "url", "url-dns", "url-connection", "urllib-http-408", "urllib-http-429", "urllib-http-503",
    "request-timeout", "request-connection", "requests-http-408", "requests-http-429",
    "requests-http-500", "timeout", "connection", "pool-timeout", "db-disconnected",
])
@pytest.mark.parametrize("phase", ["master", "collector"])
def test_g07_retryable_types_are_bounded_attempts(g07_cycle, kind, phase):
    runner, config, trace, waits, _ = g07_cycle([_g07_error(kind) for _ in range(3)], phase=phase)

    assert runner.run_forever(max_runs=3) == 3

    entries = load_schedule_status(config).recent_entries
    assert waits == [300, 300]
    assert [entry["event"] for entry in entries] == [
        "collection_started", "collection_failed", "collection_waiting",
        "collection_started", "collection_failed", "collection_waiting",
        "collection_started", "collection_failed",
    ]
    assert trace.count("sync") == 3
    assert trace.count("collector") == (3 if phase == "collector" else 0)
    assert load_schedule_status(config).total_logged_runs == 0


@pytest.mark.parametrize("kind", [
    "value", "yaml", "type", "key", "attribute", "unimplemented", "recursion",
    "assertion", "unknown", "unknown-runtime", "permission", "file", "os", "interrupt", "exit",
    "url-permission", "url-missing-file", "url-ssl", "request-ssl", "request-http-unknown",
    "urllib-http-400", "urllib-http-401", "urllib-http-403", "urllib-http-404",
    "requests-http-400", "requests-http-401", "requests-http-403", "requests-http-404", "requests-http-422",
    "db-unknown", "db-programming",
])
@pytest.mark.parametrize("phase", ["master", "collector"])
def test_g07_permanent_unknown_and_control_errors_are_not_retried(g07_cycle, phase, kind):
    error = _g07_error(kind)
    runner, _, trace, waits, _ = g07_cycle([error], phase=phase)

    with pytest.raises(type(error)) as caught:
        runner.run_forever(max_runs=3)

    assert caught.value is error
    assert waits == []
    assert trace == (["sync"] if phase == "master" else ["sync", "collector"])


@pytest.mark.parametrize("startup", [True, False])
def test_g07_zero_attempts_has_no_work_or_log(g07_cycle, startup):
    runner, _, trace, waits, _ = g07_cycle([], startup=startup)

    assert runner.run_forever(max_runs=0) == 0
    assert trace == waits == []
    assert not runner.schedule.log_path.exists()


def test_g07_false_startup_waits_before_first_failure_and_after_it(g07_cycle):
    runner, config, trace, waits, _ = g07_cycle(
        [RuntimeError("master unavailable"), {"success_count": 1, "failed_count": 0}],
        startup=False, phase="master",
    )

    assert runner.run_forever(max_runs=2) == 2

    entries = load_schedule_status(config).recent_entries
    assert trace == ["sleep", "sync", "sleep", "sync", "collector"]
    assert waits == [300, 300]
    assert entries[0]["event"] == "collection_waiting"
    assert entries[0]["next_run_at"] == "2026-10-29T09:05:00"
    assert entries[3]["next_run_at"] == "2026-10-29T09:10:02"


@pytest.mark.parametrize("failed_count", [1, 2])
def test_g07_partial_and_total_symbol_failure_dicts_are_completed_once(g07_cycle, failed_count):
    result = {"success_count": 2 - failed_count, "failed_count": failed_count}
    runner, config, trace, waits, _ = g07_cycle([result, result])

    assert runner.run_forever(max_runs=2) == 2

    status = load_schedule_status(config)
    assert status.total_logged_runs == 2
    assert status.last_failed_count == failed_count
    assert status.last_success_count == 2 - failed_count
    assert waits == [300]
    assert trace.count("collector") == 2
    assert all(entry["event"] != "collection_failed" for entry in status.recent_entries)


@pytest.mark.parametrize("kind", ["runtime", "url", "requests-http-429", "value"])
def test_g07_once_cli_preserves_failure(g07_cycle, monkeypatch, kind):
    error = _g07_error(kind)
    runner, config, _, waits, _ = g07_cycle([error])
    monkeypatch.setattr(sys, "argv", ["scheduler", "--config", str(config), "--once"])
    monkeypatch.setattr(scheduled_collection, "ScheduledCollectionRunner", lambda **kwargs: runner)

    with pytest.raises(type(error)) as caught:
        scheduled_collection.main()

    assert caught.value is error
    assert waits == []


@pytest.mark.parametrize("location", [
    "started-log", "failed-log", "finished-log", "waiting-log", "now", "sleep",
    "failed-at", "finished-at", "next-run-at", "sleep-after-failure",
])
@pytest.mark.parametrize("error_type", [RuntimeError, PermissionError, KeyboardInterrupt, SystemExit])
def test_g07_infrastructure_and_control_errors_are_not_swallowed(g07_cycle, monkeypatch, location, error_type):
    error = error_type("mock infrastructure failure")
    outcomes = ([RuntimeError("collector unavailable")] if location in {"failed-log", "failed-at", "sleep-after-failure"} else
                [{"success_count": 1, "failed_count": 0}] * 2)
    runner, _, trace, _, _ = g07_cycle(outcomes, startup=location != "waiting-log")
    original_append = ScheduledCollectionRunner._append_log
    events = []

    def append(self, payload):
        events.append(payload["event"])
        if payload["event"] == {
            "started-log": "collection_started", "failed-log": "collection_failed",
            "finished-log": "collection_finished", "waiting-log": "collection_waiting",
        }.get(location):
            raise error
        original_append(self, payload)

    def fail(*args):
        raise error

    monkeypatch.setattr(ScheduledCollectionRunner, "_append_log", append)
    if location == "now":
        runner.now_fn = fail
    elif location in {"sleep", "sleep-after-failure"}:
        runner.sleep_fn = fail
    elif location in {"failed-at", "finished-at", "next-run-at"}:
        original_now = runner.now_fn
        calls = []

        def now():
            calls.append("now")
            if len(calls) == (3 if location == "next-run-at" else 2):
                raise error
            return original_now()

        runner.now_fn = now

    with pytest.raises(error_type) as caught:
        runner.run_forever(max_runs=2)

    assert caught.value is error
    assert trace.count("collector") <= 1
    assert events.count("collection_started") <= 1


def test_g07_unbounded_runner_recovers_until_explicit_control_exit(g07_cycle):
    runner, config, trace, waits, _ = g07_cycle([
        RuntimeError("collector unavailable"),
        {"success_count": 1, "failed_count": 0},
        KeyboardInterrupt(),
    ])

    with pytest.raises(KeyboardInterrupt):
        runner.run_forever()

    assert waits == [300, 300]
    assert trace.count("collector") == 3
    assert load_schedule_status(config).total_logged_runs == 1


def test_g07_invalid_collector_result_is_not_retried(g07_cycle):
    runner, _, trace, waits, _ = g07_cycle([None])

    with pytest.raises(AttributeError):
        runner.run_forever(max_runs=2)

    assert waits == []
    assert trace == ["sync", "collector"]


@pytest.mark.parametrize("phase", ["master", "collector"])
@pytest.mark.parametrize("error_type", [ssl.SSLCertVerificationError, ssl.SSLError])
def test_g07_wrapped_ssl_failure_stops_before_wait_or_success(g07_cycle, phase, error_type):
    error = URLError(error_type("mock TLS failure"))
    runner, config, trace, waits, _ = g07_cycle(
        [error, {"success_count": 1, "failed_count": 0}], phase=phase,
    )

    with pytest.raises(URLError) as caught:
        runner.run_forever(max_runs=2)

    assert caught.value is error
    assert waits == []
    assert trace == (["sync"] if phase == "master" else ["sync", "collector"])
    assert load_schedule_status(config).total_logged_runs == 0


def test_g07_once_wrapper_subprocess_exits_nonzero(g07_cycle):
    runner, config, _, _, _ = g07_cycle([])
    script = scheduled_collection.CONFIG_DIR.parent / "scripts" / "run_scheduled_collection.py"
    code = """
import runpy
import sys
from unittest.mock import Mock
from invest_bot.jobs import scheduled_collection as module

runner_type = module.ScheduledCollectionRunner
def runner(schedule, before_run_fn):
    return runner_type(
        schedule=schedule,
        before_run_fn=Mock(side_effect=RuntimeError('master unavailable')),
        collector_fn=Mock(side_effect=AssertionError('collector must not run')),
        sleep_fn=Mock(side_effect=AssertionError('once must not sleep')),
    )
module.ScheduledCollectionRunner = runner
script = sys.argv[2]
sys.argv = [script, '--config', sys.argv[1], '--once']
runpy.run_path(script, run_name='__main__')
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(config), str(script)],
        env={**os.environ, "PYTHONPATH": str(scheduled_collection.CONFIG_DIR.parent / "src")},
        capture_output=True, text=True, timeout=10,
    )

    assert result.returncode != 0
    assert "RuntimeError: master unavailable" in result.stderr
    assert "collector must not run" not in result.stderr
    assert "once must not sleep" not in result.stderr
    assert [entry["event"] for entry in load_schedule_status(config).recent_entries] == [
        "collection_started", "collection_failed",
    ]


@pytest.mark.parametrize("field", ["days", "interval_minutes"])
@pytest.mark.parametrize("value", [0, -1, 1.5, 1.0, True, False, "1.5", "invalid", "", None])
def test_schedule_rejects_invalid_positive_integers(tmp_path, field, value):
    config_file = tmp_path / "schedule.yaml"
    config_file.write_text(
        yaml.safe_dump({"symbols": ["005930"], field: value}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match=field):
        CollectionScheduleConfig.from_file(config_file)


@pytest.mark.parametrize("value", [1, "15", " 60 "])
def test_schedule_accepts_positive_integer_values_and_numeric_strings(tmp_path, value):
    config_file = tmp_path / "schedule.yaml"
    config_file.write_text(
        yaml.safe_dump({"symbols": ["005930"], "days": value, "interval_minutes": value}),
        encoding="utf-8",
    )

    schedule = CollectionScheduleConfig.from_file(config_file)

    assert schedule.days == int(value)
    assert schedule.interval_minutes == int(value)


@pytest.mark.parametrize("value,expected", [(True, True), (False, False), ("true", True), ("false", False), (" FALSE ", False)])
def test_schedule_parses_boolean_without_python_truthiness(tmp_path, value, expected):
    config_file = tmp_path / "schedule.yaml"
    config_file.write_text(
        yaml.safe_dump({"symbols": ["005930"], "run_on_startup": value}), encoding="utf-8"
    )

    assert CollectionScheduleConfig.from_file(config_file).run_on_startup is expected


@pytest.mark.parametrize("value", [0, 1, "", "yes", "no", [], {}, None])
def test_schedule_rejects_ambiguous_boolean_values(tmp_path, value):
    config_file = tmp_path / "schedule.yaml"
    config_file.write_text(
        yaml.safe_dump({"symbols": ["005930"], "run_on_startup": value}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="run_on_startup"):
        CollectionScheduleConfig.from_file(config_file)


@pytest.mark.parametrize("text", [
    "- not-a-mapping\n", "false\n", "0\n", "symbols: 5930\n",
    "symbols: {code: '005930'}\n", "symbols: [true]\n",
    "symbols: [[005930]]\n", "symbols: ['005930']\nsymbols_file: true\n",
    "symbols: ['005930']\nlog_path: []\n", "symbols: ['005930']\nlog_path: null\n",
])
def test_schedule_rejects_wrong_yaml_types(tmp_path, text):
    config_file = tmp_path / "schedule.yaml"
    config_file.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError):
        CollectionScheduleConfig.from_file(config_file)


def test_schedule_preserves_csv_symbols_file_deduplication_and_relative_log(tmp_path):
    (tmp_path / "symbols.csv").write_text("000660\n035420\n005930\n", encoding="utf-8")
    config_file = tmp_path / "schedule.yaml"
    config_file.write_text(
        "symbols: '005930,000660'\nsymbols_file: symbols.csv\nlog_path: ../runtime/collection.log\n",
        encoding="utf-8",
    )

    schedule = CollectionScheduleConfig.from_file(config_file)

    assert schedule.symbols == ["005930", "000660", "035420"]
    assert schedule.log_path == tmp_path / ".." / "runtime" / "collection.log"
    assert schedule.days == 365
    assert schedule.interval_minutes == 1440
    assert schedule.run_on_startup is True


@pytest.mark.parametrize("args,count,waits", [
    (["--once"], 1, []),
    (["--max-runs", "2"], 2, [60, 60]),
])
def test_schedule_main_preserves_once_and_normal_loop(tmp_path, monkeypatch, args, count, waits):
    config_file = tmp_path / "schedule.yaml"
    config_file.write_text(
        "symbols: ['005930']\nrun_on_startup: false\ninterval_minutes: 1\nlog_path: collection.log\n",
        encoding="utf-8",
    )
    collected = []
    synced = []
    sleeps = []

    def collector(symbols, days):
        collected.append((symbols, days))
        return {"success_count": 1, "failed_count": 0}

    def runner(schedule, before_run_fn):
        return ScheduledCollectionRunner(
            schedule=schedule, before_run_fn=before_run_fn,
            collector_fn=collector, sleep_fn=sleeps.append,
        )

    monkeypatch.setattr(sys, "argv", ["scheduler", "--config", str(config_file), *args])
    monkeypatch.setattr(scheduled_collection, "sync_stock_master", lambda: synced.append("sync"))
    monkeypatch.setattr(scheduled_collection, "ScheduledCollectionRunner", runner)

    scheduled_collection.main()

    assert collected == [(["005930"], 365)] * count
    assert synced == ["sync"] * count
    assert sleeps == waits
    assert load_schedule_status(config_file).total_logged_runs == count


def test_collection_schedule_config_loads_symbols_and_symbols_file():
    test_dir = make_test_dir("scheduled_collection_config")
    symbols_file = test_dir / "symbols.txt"
    symbols_file.write_text("005930\n000660\n005930\n", encoding="utf-8")

    config_file = test_dir / "collection_schedule.yaml"
    config_file.write_text(
        "\n".join(
            [
                "symbols:",
                "  - '035420'",
                f"symbols_file: {symbols_file.name}",
                "days: 15",
                "interval_minutes: 60",
                "run_on_startup: false",
                "log_path: logs/custom_collection.log",
            ]
        ),
        encoding="utf-8",
    )

    config = CollectionScheduleConfig.from_file(config_file)

    assert config.symbols == ["035420", "005930", "000660"]
    assert config.days == 15
    assert config.interval_minutes == 60
    assert config.run_on_startup is False
    assert config.log_path.name == "custom_collection.log"



def test_collection_schedule_config_defaults_to_365_days_when_omitted():
    test_dir = make_test_dir("scheduled_collection_default_days")
    config_file = test_dir / "collection_schedule.yaml"
    config_file.write_text("symbols:\n  - '005930'\n", encoding="utf-8")

    config = CollectionScheduleConfig.from_file(config_file)

    assert DEFAULT_COLLECTION_LOOKBACK_DAYS == 365
    assert config.days == 365
    expected_log_path = config_file.parent.parent / ".runtime" / "logs" / "collection_scheduler.log"
    assert config.log_path.resolve() == expected_log_path.resolve()

def test_scheduled_collection_runner_runs_once_and_writes_logs():
    test_dir = make_test_dir("scheduled_collection_once")
    config = CollectionScheduleConfig(
        symbols=["005930", "000660"],
        days=20,
        interval_minutes=30,
        log_path=test_dir / "collection.log",
    )

    calls: list[tuple[list[str], int]] = []

    def collector_fn(symbols: list[str], days: int) -> dict[str, object]:
        calls.append((symbols, days))
        return {
            "symbols": symbols,
            "success_count": 2,
            "failed_count": 0,
        }

    runner = ScheduledCollectionRunner(
        schedule=config,
        collector_fn=collector_fn,
        now_fn=lambda: datetime(2026, 5, 31, 15, 30, 0),
    )
    result = runner.run_once()

    assert calls == [(["005930", "000660"], 20)]
    assert result["success_count"] == 2

    lines = config.log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "collection_started"
    assert json.loads(lines[1])["event"] == "collection_finished"


def test_scheduled_collection_runner_calls_before_run_hook():
    test_dir = make_test_dir("scheduled_collection_before_run")
    config = CollectionScheduleConfig(
        symbols=["005930"],
        days=20,
        interval_minutes=30,
        log_path=test_dir / "collection.log",
    )
    before_run_calls: list[str] = []

    runner = ScheduledCollectionRunner(
        schedule=config,
        collector_fn=lambda symbols, days: {"symbols": symbols, "success_count": 1, "failed_count": 0},
        before_run_fn=lambda: before_run_calls.append("sync"),
        now_fn=lambda: datetime(2026, 5, 31, 15, 30, 0),
    )

    runner.run_once()

    assert before_run_calls == ["sync"]


def test_scheduled_collection_runner_logs_failure_and_preserves_it_for_status():
    test_dir = make_test_dir("scheduled_collection_failure")
    config_file = test_dir / "collection_schedule.yaml"
    config_file.write_text(
        "symbols:\n  - '005930'\nlog_path: runtime/collection.log\n",
        encoding="utf-8",
    )
    config = CollectionScheduleConfig.from_file(config_file)

    def failing_collector(symbols: list[str], days: int) -> dict[str, object]:
        raise RuntimeError("collector unavailable")

    runner = ScheduledCollectionRunner(
        schedule=config,
        collector_fn=failing_collector,
        now_fn=lambda: datetime(2026, 5, 31, 15, 30, 0),
    )

    with pytest.raises(RuntimeError, match="collector unavailable"):
        runner.run_once()

    status = load_schedule_status(config_file)
    assert status.last_event == "collection_failed"
    assert status.last_failed_at == "2026-05-31T15:30:00"
    assert status.last_error == "collector unavailable"
    assert [entry["event"] for entry in status.recent_entries or []] == [
        "collection_started",
        "collection_failed",
    ]


def test_scheduled_collection_runner_appends_across_runner_restarts():
    test_dir = make_test_dir("scheduled_collection_restart")
    config_file = test_dir / "collection_schedule.yaml"
    config_file.write_text("symbols:\n  - '005930'\nlog_path: runtime/collection.log\n", encoding="utf-8")
    schedule = CollectionScheduleConfig.from_file(config_file)
    collector = lambda symbols, days: {"symbols": symbols, "success_count": 1, "failed_count": 0}

    ScheduledCollectionRunner(schedule=schedule, collector_fn=collector).run_once()
    ScheduledCollectionRunner(schedule=schedule, collector_fn=collector).run_once()

    status = load_schedule_status(config_file)
    assert schedule.log_path.parent.resolve() == (test_dir / "runtime").resolve()
    assert status.total_logged_runs == 2
    assert len(status.recent_entries or []) == 4


def test_scheduled_collection_runner_repeats_with_interval_and_max_runs():
    test_dir = make_test_dir("scheduled_collection_loop")
    config = CollectionScheduleConfig(
        symbols=["005930"],
        days=10,
        interval_minutes=5,
        run_on_startup=False,
        log_path=test_dir / "collection.log",
    )

    collector_calls: list[int] = []
    sleep_calls: list[float] = []

    def collector_fn(symbols: list[str], days: int) -> dict[str, object]:
        collector_calls.append(days)
        return {
            "symbols": symbols,
            "success_count": 1,
            "failed_count": 0,
        }

    runner = ScheduledCollectionRunner(
        schedule=config,
        collector_fn=collector_fn,
        sleep_fn=lambda seconds: sleep_calls.append(seconds),
        now_fn=lambda: datetime(2026, 5, 31, 16, 0, 0),
    )

    completed_runs = runner.run_forever(max_runs=2)

    assert completed_runs == 2
    assert collector_calls == [10, 10]
    assert sleep_calls == [300, 300]


def test_load_schedule_status_summarizes_recent_log_entries():
    test_dir = make_test_dir("scheduled_collection_status")
    config_file = test_dir / "collection_schedule.yaml"
    config_file.write_text(
        "\n".join(
            [
                "symbols:",
                "  - '005930'",
                "days: 25",
                "interval_minutes: 120",
                "run_on_startup: true",
                "log_path: collection.log",
            ]
        ),
        encoding="utf-8",
    )
    log_file = test_dir / "collection.log"
    log_file.write_text(
        "\n".join(
            [
                json.dumps({"event": "collection_started", "started_at": "2026-05-31T09:00:00"}, ensure_ascii=False),
                json.dumps(
                    {
                        "event": "collection_finished",
                        "finished_at": "2026-05-31T09:00:10",
                        "success_count": 2,
                        "failed_count": 1,
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "event": "collection_waiting",
                        "next_run_at": "2026-05-31T11:00:10",
                        "wait_seconds": 7200,
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )

    status = load_schedule_status(config_file)

    assert status.log_exists is True
    assert status.schedule.symbols == ["005930"]
    assert status.last_event == "collection_waiting"
    assert status.last_started_at == "2026-05-31T09:00:00"
    assert status.last_finished_at == "2026-05-31T09:00:10"
    assert status.next_run_at == "2026-05-31T11:00:10"
    assert status.last_success_count == 2
    assert status.last_failed_count == 1
    assert status.total_logged_runs == 1
    assert status.recent_entries is not None
    assert len(status.recent_entries) == 3
