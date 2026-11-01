"""Independent G07b QA: real shell/helper/probe, synthetic Docker/HTTP only."""
from __future__ import annotations

import builtins
import http.client
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import yaml

from scripts import service_readiness as target

ROOT = Path(__file__).resolve().parents[1]
SECRET = "QA_ONLY_SECRET_NOT_A_CREDENTIAL_83479"


def probe(monkeypatch, *, host="0.0.0.0", port="8000", base="", ssl=False,
          status=200, body=b"ok", fault=None):
    """Execute the shipped probe; application imports and network are forbidden."""
    events, forbidden = [], []
    package = ModuleType("streamlit")
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith(("invest_bot", "sqlalchemy", "requests", "streamlit_app", "scripts.")):
            forbidden.append(name)
            raise AssertionError("application/job import")
        return original_import(name, *args, **kwargs)

    def config(name):
        if fault == "config":
            raise RuntimeError(SECRET)
        return {"server.baseUrlPath": base, "server.sslCertFile": "cert" if ssl else ""}[name]

    def connection(scheme, address, number, timeout):
        events.append(("connect", scheme, address, number, timeout))
        if fault == "connect":
            raise ValueError(SECRET)

        def request(method, path):
            events.append(("request", method, path))
            if fault == "request":
                raise OSError(SECRET)

        def response():
            if fault == "response":
                raise http.client.HTTPException(SECRET)
            return SimpleNamespace(status=status, read=read)

        def read(size):
            events.append(("read", size))
            if fault == "read":
                raise OSError(SECRET)
            return body[:size]

        return SimpleNamespace(request=request, getresponse=response,
                               close=lambda: events.append(("close",)))

    package.config = SimpleNamespace(get_option=config)
    with monkeypatch.context() as local:
        local.setitem(sys.modules, "streamlit", package)
        local.setenv("INVEST_BOT_DASHBOARD_HOST", host)
        local.setenv("INVEST_BOT_DASHBOARD_PORT", port)
        local.setattr(sys, "argv", ["qa-probe", "1.25"])
        local.setattr(builtins, "__import__", guarded_import)
        local.setattr(http.client, "HTTPConnection", lambda *a, **k: connection("http", *a, **k))
        local.setattr(http.client, "HTTPSConnection", lambda *a, **k: connection("https", *a, **k))
        with pytest.raises(SystemExit) as result:
            exec(compile(target.HTTP_PROBE, "<actual-shipped-probe>", "exec"), {})
    assert forbidden == []
    return result.value.code, events


class Scenario:
    """Drive real Startup orchestration, not an isolated status classifier."""
    def __init__(self, *, mutate=None, http=None, costs=None, up=0, fault=None, outputs=None):
        self.now, self.round = 40.0, 0
        self.waits, self.calls, self.snapshots = [], [], {}
        self.mutate, self.http = mutate, http
        self.costs, self.up = costs or {}, up
        self.fault, self.outputs = fault, outputs or {}
        self.startup = target.Startup(target.Options(8, .5, 1, 2), execute=self.execute,
                                      clock=lambda: self.now, sleep=self.sleep)

    def sleep(self, seconds):
        assert 0 < seconds <= .5
        self.waits.append(seconds)
        self.now += seconds

    def execute(self, argv, timeout):
        stage = argv[2] if argv[1] == "compose" else argv[1]
        assert stage in {"down", "up", "ps", "inspect", "exec"}
        self.calls.append((stage, list(argv), timeout, self.now))
        assert 0 < timeout <= self.startup.deadline - self.now
        if stage not in {"down", "up"}:
            assert timeout <= 2
        spent = self.costs.get(stage, 0)
        self.now += min(spent, timeout)
        if spent > timeout:
            raise subprocess.TimeoutExpired(argv, timeout, output=SECRET, stderr=SECRET)
        if self.fault and self.fault[0] == stage:
            kind = self.fault[1]
            if kind == "timeout":
                raise subprocess.TimeoutExpired(argv, timeout, output=SECRET)
            if kind == "missing-cli":
                raise OSError(SECRET)
            if kind == "encoding":
                raise UnicodeDecodeError("utf8", b"\xff", 0, 1, SECRET)
            return subprocess.CompletedProcess(argv, int(kind), SECRET, SECRET)
        value, code = "", 0
        if stage == "up":
            code = self.up
        elif stage == "ps":
            service = argv[-1]
            assert argv == ["docker", "compose", "ps", "--all", "--quiet", service]
            if service == "db":
                self.round += 1
            identity = {"db": "d", "migrate": "a", "web": "b", "scheduler": "c"}[service] * 64
            data = [identity, "exited" if service == "migrate" else "running", 0, 0,
                    "2026-10-31T12:00:00Z", "healthy" if service == "db" else "none"]
            if self.mutate:
                self.mutate(service, self.round, data)
            self.snapshots[data[0]] = data
            value = self.outputs.get(("ps", service), data[0])
        elif stage == "inspect":
            assert argv[2:6] == ["--type", "container", "--format", target.INSPECT_FORMAT]
            value = self.outputs.get(("inspect", "any"), "|".join(map(str, self.snapshots[argv[-1]])))
        elif stage == "exec":
            assert argv[2] == "b" * 64
            assert argv[3:8] == ["python", "-I", "-B", "-c", target.HTTP_PROBE]
            assert 0 < float(argv[8]) <= 2
            code = self.http(self.round) if self.http else 0
        return subprocess.CompletedProcess(argv, code, value, SECRET)

    def run(self, restart=False):
        self.startup.start(restart=restart)


def test_delayed_orchestration_executes_actual_probe(monkeypatch):
    traces = []

    def mutate(service, n, data):
        if n < 3 and service == "migrate":
            data[1] = "running"
        if n < 3 and service == "db":
            data[5] = "starting"

    def http(n):
        code, observed = probe(monkeypatch, status=503 if n < 3 else 200, base="research")
        traces.extend(observed)
        return code

    scenario = Scenario(mutate=mutate, http=http)
    scenario.run()
    assert scenario.round == 3 and scenario.waits == [.5, .5] and scenario.now == 41
    assert traces.count(("request", "GET", "/research/_stcore/health")) == 3


@pytest.mark.parametrize("state", ["exited", "restarting", "dead", "paused", "removing"])
def test_scheduler_bad_state_never_confirms(state):
    def mutate(service, n, data):
        if service == "scheduler" and n >= 2:
            data[1] = state
    scenario = Scenario(mutate=mutate)
    with pytest.raises(target.ReadinessError, match="scheduler"):
        scenario.run()
    assert scenario.round == 2 and all(x[0] != "down" for x in scenario.calls)


@pytest.mark.parametrize("field,value", [(0, "e" * 64), (3, 1), (4, "2026-10-31T12:00:01Z")])
def test_scheduler_change_cannot_reuse_previous_stability(field, value):
    def mutate(service, n, data):
        if service == "scheduler" and n >= 2:
            data[field] = value
    scenario = Scenario(mutate=mutate)
    with pytest.raises(target.ReadinessError, match="restarted or replaced"):
        scenario.run()
    assert scenario.now == 40.5


def test_running_scheduler_requires_positive_interval_not_job_success():
    # Long collection and interval wait are indistinguishable: no last-success
    # source, application settings, jobs or collectors are supplied or queried.
    scenario = Scenario()
    scenario.run()
    assert scenario.now - 40 >= 1 and scenario.round >= 2 and scenario.waits
    assert {x[0] for x in scenario.calls} == {"up", "ps", "inspect", "exec"}


@pytest.mark.parametrize("waiting", ["migrate", "web"])
def test_endless_readiness_uses_only_initial_budget(waiting):
    def mutate(service, n, data):
        if waiting == "migrate" and service == "migrate":
            data[1] = "running"
    scenario = Scenario(mutate=mutate, http=(lambda n: 75) if waiting == "web" else None)
    with pytest.raises(target.ReadinessError, match="deadline exceeded") as error:
        scenario.run()
    assert error.value.code == 124 and scenario.now == 48 and sum(scenario.waits) == 8
    assert all(x[0] != "down" for x in scenario.calls)


def test_migrate_nonzero_fatal_without_extra_jobs():
    def mutate(service, n, data):
        if service == "migrate":
            data[2] = 27
    scenario = Scenario(mutate=mutate)
    with pytest.raises(target.ReadinessError, match="migrate: unsuccessful"):
        scenario.run()
    assert not scenario.waits and {x[0] for x in scenario.calls} == {"up", "ps", "inspect"}


def test_down_up_queries_share_one_budget():
    scenario = Scenario(costs={"down": 2, "up": 3})
    scenario.run(restart=True)
    assert [(x[0], x[2]) for x in scenario.calls[:2]] == [("down", 8), ("up", 6)]
    assert scenario.startup.deadline == 48 and scenario.now == 46
    assert all(x[2] <= min(2, 48 - x[3]) for x in scenario.calls[2:])


@pytest.mark.parametrize("stage", ["down", "up", "ps", "inspect", "exec"])
def test_command_timeout_has_no_diagnostic_or_cleanup_tail(stage):
    scenario = Scenario(fault=(stage, "timeout"))
    with pytest.raises(target.ReadinessError, match="timed out") as error:
        scenario.run(restart=stage == "down")
    assert error.value.code == 124 and scenario.calls[-1][0] == stage
    assert SECRET not in str(error.value)
    assert [x[0] for x in scenario.calls].count("down") == (stage == "down")
    assert scenario.calls[-1][2] == (8 if stage in {"up", "down"} else 2)


@pytest.mark.parametrize("stage", ["ps", "inspect", "exec"])
def test_individual_cap_clamped_to_remaining(stage):
    scenario = Scenario(costs={"up": 7}, fault=(stage, "timeout"))
    with pytest.raises(target.ReadinessError) as error:
        scenario.run()
    assert error.value.code == 124
    assert scenario.calls[-1][0] == stage and scenario.calls[-1][2] == 1


@pytest.mark.parametrize("kind", [17, "missing-cli", "encoding"])
def test_query_errors_fail_closed_without_echo(kind):
    scenario = Scenario(fault=("ps", kind))
    with pytest.raises(target.ReadinessError) as error:
        scenario.run()
    assert SECRET not in str(error.value) and len(scenario.calls) == 2


@pytest.mark.parametrize("response", ["", "a" * 64 + "\n" + "b" * 64, "NOT-A-CONTAINER", "A" * 64])
def test_missing_ambiguous_or_invalid_ids_never_pass(response):
    scenario = Scenario(outputs={("ps", "db"): response})
    with pytest.raises(target.ReadinessError):
        scenario.run()
    assert scenario.calls[-1][0] == "ps"


@pytest.mark.parametrize("response", [SECRET, "d" * 64 + "|running|0", "|running|0|0|bad|healthy",
    "d" * 64 + "|running|0|-1|2026-10-31T12:00:00Z|healthy",
    "d" * 64 + "|running|0|0|2026-10-31T12:00:00|healthy",
    "d" * 64 + "|running|0|0|2026-10-31T12:00:00Z|unknown"])
def test_malformed_inspect_not_success(response):
    scenario = Scenario(outputs={("inspect", "any"): response})
    with pytest.raises(target.ReadinessError, match="invalid state response") as error:
        scenario.run()
    assert SECRET not in str(error.value)


def test_up_failure_missing_migrate_identifies_db_preserving_exit():
    def mutate(service, n, data):
        if service == "db":
            data[5] = "unhealthy"
    scenario = Scenario(up=47, mutate=mutate, outputs={("ps", "migrate"): ""})
    with pytest.raises(target.ReadinessError, match="up: db health check failed") as error:
        scenario.run()
    assert error.value.code == 47
    assert [x[1][-1] for x in scenario.calls if x[0] == "ps"] == ["migrate", "db"]
    assert not scenario.waits


@pytest.mark.parametrize("kind", ["query-failed", "query-timeout", "budget-spent", "malformed"])
def test_diagnosis_cannot_replace_original_up_failure(kind):
    kwargs = {"up": 47}
    if kind == "query-failed":
        kwargs["fault"] = ("ps", 23)
    elif kind == "query-timeout":
        kwargs["fault"] = ("ps", "timeout")
    elif kind == "budget-spent":
        kwargs["costs"] = {"up": 7.5, "ps": .75}
    else:
        kwargs["outputs"] = {("inspect", "any"): SECRET}
    scenario = Scenario(**kwargs)
    with pytest.raises(target.ReadinessError, match="up: Docker command failed") as error:
        scenario.run()
    assert error.value.code == 47 and SECRET not in str(error.value)
    assert len(scenario.calls) <= 3 and scenario.now <= 48


@pytest.mark.parametrize("host,expected", [("0.0.0.0", "127.0.0.1"), ("::", "::1"),
    ("[::]", "::1"), ("::1", "::1"), ("dashboard.internal", "dashboard.internal"),
    (" 192.0.2.15 ", "192.0.2.15"), ("  ", "127.0.0.1")])
def test_probe_maps_bind_and_base_without_network(monkeypatch, host, expected):
    code, events = probe(monkeypatch, host=host, port=" 8012 ", base="/qa path/분석/")
    assert code == 0 and ("connect", "http", expected, 8012, 1.25) in events
    assert ("request", "GET", "/qa%20path/%EB%B6%84%EC%84%9D/_stcore/health") in events
    assert events[-1] == ("close",)


@pytest.mark.parametrize("value,expected,code", [("not-numeric", 8000, 0), ("", 8000, 0),
    ("8000.0", 8000, 0), ("65535", 65535, 0), ("0", None, 70), ("65536", None, 70), ("-1", None, 70)])
def test_probe_numeric_fallback_and_invalid_bind(monkeypatch, value, expected, code):
    actual, events = probe(monkeypatch, port=value)
    assert actual == code
    assert [x for x in events if x[0] == "connect"] == (
        [] if expected is None else [("connect", "http", "127.0.0.1", expected, 1.25)])


@pytest.mark.parametrize("ssl", [False, True])
def test_probe_uses_current_tls_config(monkeypatch, ssl):
    code, events = probe(monkeypatch, ssl=ssl)
    assert code == 0
    assert events[0] == ("connect", "https" if ssl else "http", "127.0.0.1", 8000, 1.25)


@pytest.mark.parametrize("status,body,expected", [(200, b"ok", 0), (200, b"ok\n", 75),
    (200, b"", 75), (200, b"OK", 75), (200, b"ok" + b"x" * 30, 75), (503, b"ok", 75), (302, b"ok", 75)])
def test_probe_requires_status_and_exact_body(monkeypatch, status, body, expected):
    code, events = probe(monkeypatch, status=status, body=body)
    assert code == expected and events[-1] == ("close",)


@pytest.mark.parametrize("fault,expected", [("config", 70), ("connect", 70),
    ("request", 75), ("response", 75), ("read", 75)])
def test_probe_exceptions_fail_closed_without_payload(monkeypatch, capsys, fault, expected):
    code, events = probe(monkeypatch, fault=fault)
    assert code == expected
    if fault not in {"config", "connect"}:
        assert events[-1] == ("close",)
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err


@pytest.mark.parametrize("code", [70, 75])
def test_actual_probe_failure_connects_to_startup(monkeypatch, code):
    def http(n):
        actual, _ = probe(monkeypatch, fault="config" if code == 70 else "request")
        assert actual == code
        return actual
    scenario = Scenario(http=http)
    with pytest.raises(target.ReadinessError) as error:
        scenario.run()
    assert error.value.code == (70 if code == 70 else 124)
    assert "web HTTP" in str(error.value)


@pytest.mark.parametrize("key", ["TIMEOUT", "POLL", "STABLE", "COMMAND_TIMEOUT"])
@pytest.mark.parametrize("bad", ["0", "-1", "+1", " 1", "1 ", "1e2", "NaN", "Infinity", "１", "86400.1", SECRET])
def test_durations_ascii_positive_bounded_redacted(key, bad):
    with pytest.raises(target.ReadinessError) as error:
        target.Options.from_env({"INVEST_BOT_START_" + key + "_SECONDS": bad})
    assert SECRET not in str(error.value)


@pytest.mark.parametrize("values", [(8, 2, 1, 2), (8, 1, 8, 2), (8, 1, 2, 9)])
def test_duration_relations_never_skip_observation(values):
    env = {"INVEST_BOT_START_" + key + "_SECONDS": str(value)
           for key, value in zip(["TIMEOUT", "POLL", "STABLE", "COMMAND_TIMEOUT"], values)}
    with pytest.raises(target.ReadinessError):
        target.Options.from_env(env)


def test_host_check_defaults_without_dotenv(monkeypatch, tmp_path, capsys):
    (tmp_path / ".env").write_text("INVEST_BOT_START_TIMEOUT_SECONDS=0\n" + SECRET)
    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith("INVEST_BOT_START_"):
            monkeypatch.delenv(key)
    monkeypatch.setattr(sys, "argv", ["readiness", "--check"])
    monkeypatch.setattr(target, "Startup", lambda *a, **k: pytest.fail("check started Docker"))
    assert target.Options.from_env(os.environ) == target.Options(180, 1, 10, 5)
    assert target.main() == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == target.CHECK_RESPONSE and not captured.err


def test_native_timeout_kills_cli_group_and_reaps(monkeypatch):
    original_popen, original_kill = subprocess.Popen, os.killpg
    processes, killed = [], []

    def popen(*args, **kwargs):
        assert kwargs["start_new_session"] is True
        result = original_popen(*args, **kwargs)
        processes.append(result)
        return result

    def kill(group, sig):
        killed.append((group, sig))
        return original_kill(group, sig)

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(os, "killpg", kill)
    before = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        target.run_command([sys.executable, "-B", "-c", "import signal; signal.alarm(2); signal.pause()"], .06)
    assert time.monotonic() - before < .06 + .4 + .2
    assert len(processes) == 1 and processes[0].poll() is not None
    assert killed == [(processes[0].pid, signal.SIGKILL)]


def test_worst_case_native_cleanup_grace_bounded(monkeypatch):
    calls = []

    class VirtualProcess:
        pid = 987654321
        stdout = SimpleNamespace(close=lambda: calls.append(("close",)))

        def communicate(self, timeout):
            calls.append(("communicate", timeout))
            raise subprocess.TimeoutExpired("virtual-cli", timeout)

        def wait(self, timeout):
            calls.append(("wait", timeout))
            raise subprocess.TimeoutExpired("virtual-cli", timeout)

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: VirtualProcess())
    monkeypatch.setattr(os, "killpg", lambda group, sig: calls.append(("kill", group, sig)))
    with pytest.raises(subprocess.TimeoutExpired):
        target.run_command(["virtual-cli"], .03)
    assert calls == [("communicate", .03), ("kill", 987654321, signal.SIGKILL),
                     ("communicate", .2), ("close",), ("wait", .2)]


@pytest.fixture
def isolated_shell(tmp_path):
    project = tmp_path / "isolated project with spaces"
    project.mkdir()
    (project / "config").mkdir()
    (project / "config/collection_schedule.yaml").write_text("symbols: ['005930']\n")
    (project / "scripts").mkdir()
    for name in ("start.sh", "restart.sh", "stop.sh", "scripts/service_readiness.py"):
        shutil.copy2(ROOT / name, project / name)
    binaries = tmp_path / "fake executables"
    binaries.mkdir()
    state, case, log = (tmp_path / name for name in ("state.json", "case.json", "calls.jsonl"))
    state.write_text(json.dumps({"t": 100.0, "round": 0}))
    case.write_text("{}")
    runtime = binaries / "qa python"
    runtime.write_text(f'''#!{sys.executable}
import json, os, runpy, subprocess, sys, time
from pathlib import Path
state = Path(os.environ['QA_STATE'])
case = json.loads(Path(os.environ['QA_CASE']).read_text())
if not case.get('native_clock'):
    def clock():
        return json.loads(state.read_text())['t']
    def sleep(seconds):
        data = json.loads(state.read_text()); data['t'] += seconds
        state.write_text(json.dumps(data))
    time.monotonic = clock
    time.sleep = sleep
args = sys.argv[1:]
if args[0] == '-B': args = args[1:]
sys.argv = args
runpy.run_path(args[0], run_name='__main__')
''')
    runtime.chmod(0o755)
    docker = binaries / "docker"
    docker.write_text(f'''#!{sys.executable}
import http.client, json, os, signal, sys, types
from pathlib import Path
args = sys.argv[1:]
state_path = Path(os.environ['QA_STATE'])
data = json.loads(state_path.read_text())
case = json.loads(Path(os.environ['QA_CASE']).read_text())
stage = args[1] if args[0] == 'compose' else args[0]
assert stage in {{'config','build','run','down','up','ps','inspect','exec','stop'}}
def record(entry):
    with open(os.environ['QA_LOG'], 'a') as handle:
        handle.write(json.dumps(entry) + '\\n')
record({{'args': args, 'cwd': os.getcwd(), 't': data['t']}})
data['t'] += case.get('costs', {{}}).get(stage, 0)
if stage == 'ps' and args[-1] == 'db': data['round'] += 1
state_path.write_text(json.dumps(data))
if case.get('hang') == stage:
    signal.alarm(2); signal.pause()
if case.get('fail') == stage:
    if stage not in {{'config','build','run'}}: print({SECRET!r}, file=sys.stderr)
    sys.exit(case.get('code', 47))
if stage in {{'config','build','run','stop'}}: sys.exit(0)
print({SECRET!r}, file=sys.stderr)
mode = case.get('mode', 'healthy')
ids = {{'db':'d'*64,'migrate':'a'*64,'web':'b'*64,'scheduler':'c'*64}}
if stage == 'ps':
    if mode == 'missing-migrate-db-bad' and args[-1] == 'migrate': sys.exit(0)
    identity = ids[args[-1]]
    if mode == 'replace' and args[-1] == 'scheduler' and data['round'] > 1: identity = 'e' * 64
    print(identity)
elif stage == 'inspect':
    if mode == 'invalid-inspect':
        print({SECRET!r}); sys.exit(0)
    identity = args[-1]
    service = {{'a':'migrate','b':'web','c':'scheduler','d':'db','e':'scheduler'}}[identity[0]]
    status, code, count, stamp, health = 'running',0,0,'2026-10-31T12:00:00Z','none'
    if service == 'migrate':
        status = 'running' if mode == 'migration-wait' or (mode == 'delayed' and data['round'] < 3) else 'exited'
        code = 19 if mode == 'migration-fail' else 0
    if service == 'db': health = 'unhealthy' if mode == 'missing-migrate-db-bad' else 'healthy'
    if service == 'scheduler' and data['round'] > 1:
        if mode == 'exited': status = 'exited'
        if mode == 'restarting': status = 'restarting'
        if mode == 'restart-count': count = 1
        if mode == 'start-time': stamp = '2026-10-31T12:00:01Z'
    print('|'.join(map(str, (identity,status,code,count,stamp,health))))
elif stage == 'exec':
    assert args[1] == ids['web'] and args[2:6] == ['python','-I','-B','-c']
    streamlit = types.ModuleType('streamlit')
    def option(name):
        if mode == 'http-config': raise RuntimeError({SECRET!r})
        return 'qa/base' if name == 'server.baseUrlPath' else ''
    streamlit.config = types.SimpleNamespace(get_option=option)
    sys.modules['streamlit'] = streamlit
    def connection(host, port, timeout):
        record({{'http': [host, port, timeout]}})
        def request(method, path):
            record({{'request': [method, path]}})
            if mode == 'http-error': raise OSError({SECRET!r})
        status = 503 if mode == 'http-wait' or (mode == 'delayed' and data['round'] < 3) else 200
        response = types.SimpleNamespace(status=status, read=lambda size: b'ok')
        return types.SimpleNamespace(request=request, getresponse=lambda: response, close=lambda: None)
    http.client.HTTPConnection = connection
    http.client.HTTPSConnection = connection
    sys.argv = ['probe', args[-1]]
    exec(compile(args[-2], '<actual-shipped-probe>', 'exec'), {{}})
''')
    docker.chmod(0o755)
    outside = tmp_path / "outside project"
    outside.mkdir()
    env = {"PATH": f"{binaries}:/usr/bin:/bin", "TMPDIR": "/private/tmp",
           "PYTHONDONTWRITEBYTECODE": "1", "INVEST_BOT_PYTHON": str(runtime),
           "QA_STATE": str(state), "QA_CASE": str(case), "QA_LOG": str(log),
           "INVEST_BOT_DASHBOARD_HOST": "0.0.0.0", "INVEST_BOT_DASHBOARD_PORT": "8000",
           "INVEST_BOT_START_TIMEOUT_SECONDS": "8", "INVEST_BOT_START_POLL_SECONDS": ".5",
           "INVEST_BOT_START_STABLE_SECONDS": "1", "INVEST_BOT_START_COMMAND_TIMEOUT_SECONDS": "2"}

    def run(name="start.sh", **settings):
        case.write_text(json.dumps(settings))
        result = subprocess.run(["/bin/bash", str(project / name)], cwd=outside, env=env,
                                capture_output=True, text=True, timeout=12)
        entries = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        assert SECRET not in result.stdout + result.stderr
        calls = [item for item in entries if "args" in item]
        assert all(item["cwd"] == str(project) for item in calls)
        return result, entries, json.loads(state.read_text())

    return SimpleNamespace(run=run, env=env, project=project, log=log)


@pytest.mark.parametrize("name", ["start.sh", "restart.sh"])
def test_shell_actual_helper_and_probe_delayed_success(isolated_shell, name):
    result, entries, state = isolated_shell.run(name, mode="delayed", costs={"build": 120, "run": 90})
    assert result.returncode == 0, result.stderr
    commands = [x["args"] for x in entries if "args" in x]
    assert commands[:3] == [["compose", "config", "--quiet"], ["compose", "build"],
        ["compose", "run", "--rm", "--no-deps", "scheduler", "python",
         "scripts/run_scheduled_collection.py", "--validate-config"]]
    expected = [["compose", "down"]] if name == "restart.sh" else []
    assert commands[3:4 + len(expected)] == expected + [
        ["compose", "up", "-d", "db", "migrate", "scheduler", "web"]]
    assert state == {"t": 311.0, "round": 3}
    assert [x["request"] for x in entries if "request" in x] == [["GET", "/qa/base/_stcore/health"]] * 3
    assert all(x["http"][:2] == ["127.0.0.1", 8000] for x in entries if "http" in x)
    assert "Service readiness confirmed" in result.stdout


@pytest.mark.parametrize("mode,expected", [("migration-fail", 1), ("migration-wait", 124),
    ("http-wait", 124), ("http-error", 124), ("http-config", 70), ("replace", 1),
    ("exited", 1), ("restarting", 1), ("restart-count", 1), ("start-time", 1), ("invalid-inspect", 1)])
def test_shell_failures_propagate_without_cleanup(isolated_shell, mode, expected):
    result, entries, state = isolated_shell.run(mode=mode)
    assert result.returncode == expected, result.stderr
    assert "Service readiness confirmed" not in result.stdout
    commands = [x["args"] for x in entries if "args" in x]
    assert sum(x[:2] == ["compose", "up"] for x in commands) == 1
    assert not any(x[:2] == ["compose", "down"] or "--volumes" in x for x in commands)
    assert not any("run_collection.py" in str(x) or "logs" in x for x in commands)
    if expected == 124:
        assert state["t"] == 108


@pytest.mark.parametrize("name", ["start.sh", "restart.sh"])
@pytest.mark.parametrize("bad", ["true", "echo", "missing", "duration"])
def test_runtime_handshake_before_all_docker(isolated_shell, name, bad):
    if bad in {"true", "echo"}:
        isolated_shell.env["INVEST_BOT_PYTHON"] = "/usr/bin/" + bad
    elif bad == "missing":
        isolated_shell.env["INVEST_BOT_PYTHON"] = "/nonexistent/qa-runtime"
    else:
        isolated_shell.env["INVEST_BOT_START_TIMEOUT_SECONDS"] = SECRET
    result, entries, _ = isolated_shell.run(name)
    assert result.returncode != 0 and entries == [] and not isolated_shell.log.exists()


@pytest.mark.parametrize("stage", ["config", "build", "run"])
def test_g02_fail_fast_prevents_down_up(isolated_shell, stage):
    result, entries, _ = isolated_shell.run("restart.sh", fail=stage, code=37)
    assert result.returncode == 37
    commands = [x["args"] for x in entries if "args" in x]
    assert len(commands) == ["config", "build", "run"].index(stage) + 1
    assert all(command[1] not in {"down", "up"} for command in commands)


def test_shell_restart_shared_budget_without_rollback(isolated_shell):
    result, entries, state = isolated_shell.run("restart.sh", mode="http-wait", costs={"down": 2, "up": 3})
    assert result.returncode == 124 and state["t"] == 108
    commands = [x for x in entries if "args" in x]
    assert [x["t"] for x in commands if x["args"][:2] in [
        ["compose", "down"], ["compose", "up"]]] == [100, 102]
    assert sum(x["args"][:2] == ["compose", "down"] for x in commands) == 1


def test_shell_up_missing_migrate_diagnoses_db(isolated_shell):
    result, entries, _ = isolated_shell.run(mode="missing-migrate-db-bad", fail="up", code=47)
    assert result.returncode == 47 and "up: db health check failed" in result.stderr
    commands = [x["args"] for x in entries if "args" in x]
    assert [x[-1] for x in commands if x[:2] == ["compose", "ps"]] == ["migrate", "db"]


def test_shell_native_hung_up_has_no_post_timeout_queries(isolated_shell):
    isolated_shell.env.update({"INVEST_BOT_START_TIMEOUT_SECONDS": ".25",
        "INVEST_BOT_START_POLL_SECONDS": ".01", "INVEST_BOT_START_STABLE_SECONDS": ".02",
        "INVEST_BOT_START_COMMAND_TIMEOUT_SECONDS": ".1"})
    before = time.monotonic()
    result, entries, _ = isolated_shell.run(native_clock=True, hang="up")
    assert result.returncode == 124 and "up: Docker command timed out" in result.stderr
    assert time.monotonic() - before < 2
    commands = [x["args"] for x in entries if "args" in x]
    assert commands[-1][:2] == ["compose", "up"] and len(commands) == 4


def test_stop_remains_plain_stop(isolated_shell):
    isolated_shell.env["INVEST_BOT_PYTHON"] = "/nonexistent/qa-runtime"
    result, entries, _ = isolated_shell.run("stop.sh")
    assert result.returncode == 0
    assert [x["args"] for x in entries] == [["compose", "stop"]]
    assert (isolated_shell.project / "stop.sh").read_bytes() == (ROOT / "stop.sh").read_bytes()


@pytest.mark.parametrize("stage", ["ps", "inspect", "exec"])
def test_native_individual_cli_hangs_use_cap_not_full_deadline(isolated_shell, stage):
    isolated_shell.env.update({"INVEST_BOT_START_TIMEOUT_SECONDS": "3",
        "INVEST_BOT_START_POLL_SECONDS": ".05", "INVEST_BOT_START_STABLE_SECONDS": ".1",
        "INVEST_BOT_START_COMMAND_TIMEOUT_SECONDS": ".25"})
    before = time.monotonic()
    result, entries, _ = isolated_shell.run(native_clock=True, hang=stage)
    assert result.returncode == 124 and "Docker command timed out" in result.stderr
    assert time.monotonic() - before < 2  # Full budget alone would wait three seconds.
    commands = [x["args"] for x in entries if "args" in x]
    last_stage = commands[-1][1] if commands[-1][0] == "compose" else commands[-1][0]
    assert last_stage == stage
    assert not any(x[:2] == ["compose", "down"] for x in commands)


@pytest.mark.parametrize("name", ["start.sh", "restart.sh"])
def test_missing_all_python_candidates_fails_before_docker(isolated_shell, name):
    binaries = Path(isolated_shell.env["PATH"].split(":")[0])
    (binaries / "dirname").symlink_to("/usr/bin/dirname")
    isolated_shell.env["PATH"] = str(binaries)
    isolated_shell.env.pop("INVEST_BOT_PYTHON")
    result, entries, _ = isolated_shell.run(name)
    assert result.returncode != 0 and "Python runtime not found" in result.stderr
    assert entries == []


@pytest.mark.parametrize("host_value,file_value,published", [(None, None, 8000), ("8012", None, 8012),
    ("8012", "9911", 8012), (None, "9911", 9911), ("", "9911", 8000)])
def test_compose_ports_connect_launcher_and_actual_probe(monkeypatch, host_value, file_value, published):
    from scripts.run_streamlit_dashboard import build_streamlit_argv, resolve_dashboard_bind
    web = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]["web"]
    assert web["environment"]["INVEST_BOT_DASHBOARD_PORT"] == "8000"
    assert isinstance(web["environment"]["INVEST_BOT_DASHBOARD_PORT"], str)
    expression = "$" + "{INVEST_BOT_DASHBOARD_PORT:-8000}"
    assert web["ports"] == [expression + ":8000"]
    # Only model the known expression, not an imitation Compose engine.
    value = host_value if host_value is not None else file_value
    mapping = web["ports"][0].replace(expression, value or "8000")
    assert tuple(map(int, mapping.split(":"))) == (published, 8000)
    container_env = {"INVEST_BOT_DASHBOARD_PORT": file_value or "9911", **web["environment"]}
    with monkeypatch.context() as local:
        local.delenv("INVEST_BOT_DASHBOARD_PORT", raising=False)
        local.delenv("INVEST_BOT_DASHBOARD_HOST", raising=False)
        if host_value is not None:
            local.setenv("INVEST_BOT_DASHBOARD_PORT", host_value)
        assert resolve_dashboard_bind()[1] == (int(host_value) if host_value else 8000)
    for key in ("INVEST_BOT_DASHBOARD_HOST", "INVEST_BOT_DASHBOARD_PORT"):
        monkeypatch.setenv(key, container_env[key])
    host, bound = resolve_dashboard_bind()
    argv = build_streamlit_argv(host, bound)
    assert bound == int(mapping.split(":")[1]) == 8000
    assert argv[argv.index("--server.port") + 1] == "8000"
    code, events = probe(monkeypatch, host=host, port=str(bound))
    assert code == 0 and ("connect", "http", "127.0.0.1", 8000, 1.25) in events


@pytest.mark.parametrize("version,expected", [((3, 9), 1), ((3, 10), 0)])
def test_check_enforces_minimum_host_runtime_before_docker(monkeypatch, capsys, version, expected):
    monkeypatch.setattr(sys, "argv", ["readiness", "--check"])
    monkeypatch.setattr(sys, "version_info", version)
    monkeypatch.setattr(target, "Startup", lambda *a, **k: pytest.fail("runtime check started Docker"))
    assert target.main() == expected
    captured = capsys.readouterr()
    assert ("POSIX Python 3.10" in captured.err) == (expected == 1)
