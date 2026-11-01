from __future__ import annotations

import http.client
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from scripts import service_readiness as readiness
from tests.test_operations_scripts import _run_script, shell_project


class FakeClock:
    def __init__(self):
        self.value = 0.0
        self.waits = []

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.value += seconds


class FakeDocker:
    def __init__(self, clock, *, change=None, http=None, fail=None, consume=None):
        self.clock, self.change, self.http, self.fail, self.consume = clock, change, http, fail, consume
        self.calls = []
        self.round = 0
        self.ids = {"db": "d" * 64, "migrate": "a" * 64, "web": "b" * 64, "scheduler": "c" * 64}
        self.snapshots = {}

    def __call__(self, argv, timeout):
        self.calls.append((argv, timeout))
        assert 0 < timeout <= 12
        if self.consume:
            self.consume(argv, self.clock)
        if self.fail:
            failure = self.fail(argv)
            if isinstance(failure, Exception):
                raise failure
            if failure:
                return subprocess.CompletedProcess(argv, failure, "private-payload", "private-payload")
        output, code = "", 0
        if argv[1:3] == ["compose", "ps"]:
            service = argv[-1]
            if service == "db":
                self.round += 1
            data = [self.ids[service], "running", 0, 0, "2026-10-31T00:00:00Z", "none"]
            if service == "db":
                data[5] = "healthy"
            if service == "migrate":
                data[1] = "exited"
            if self.change:
                data = self.change(service, self.round, data)
            if data is None:
                output = ""
            elif isinstance(data, str):
                output = data
            else:
                self.snapshots[data[0]] = data
                output = data[0]
        elif argv[1] == "inspect":
            output = "|".join(map(str, self.snapshots[argv[-1]]))
        elif argv[1] == "exec":
            assert argv[2] == self.ids["web"]
            assert argv[3:7] == ["python", "-I", "-B", "-c"]
            assert argv[7] == readiness.HTTP_PROBE
            code = self.http(self.round) if self.http else 0
        return subprocess.CompletedProcess(argv, code, output, "private-payload")


def setup_startup(**kwargs):
    clock = FakeClock()
    docker = FakeDocker(clock, **kwargs)
    startup = readiness.Startup(readiness.Options(12, 1, 2, 3), execute=docker, clock=clock.now, sleep=clock.sleep)
    return startup, docker, clock


def test_delayed_success_checks_all_services_and_waits_for_stability():
    def change(service, round_number, data):
        if round_number < 3:
            if service == "db":
                data[5] = "starting"
            if service == "migrate":
                data[1] = "running"
        return data

    startup, docker, clock = setup_startup(change=change, http=lambda round_number: 75 if round_number < 3 else 0)
    startup.start()
    assert clock.waits == [1, 1]
    assert docker.round == 3
    assert docker.calls[0][0] == ["docker", "compose", "up", "-d", "db", "migrate", "scheduler", "web"]
    assert docker.calls[0][1] == 12


@pytest.mark.parametrize("service,state,health", [
    ("migrate", "exited", "none"), ("db", "running", "unhealthy"), ("web", "exited", "none"),
    ("scheduler", "restarting", "none"), ("scheduler", "dead", "none"), ("scheduler", "paused", "none"),
])
def test_terminal_or_unhealthy_services_fail(service, state, health):
    def change(name, round_number, data):
        if name == service:
            data[1], data[2], data[5] = state, 1, health
        return data

    startup, _, clock = setup_startup(change=change)
    with pytest.raises(readiness.ReadinessError, match=service):
        startup.start()
    assert clock.waits == []


@pytest.mark.parametrize("field,value", [(0, "e" * 64), (3, 1), (4, "2026-10-31T00:00:01Z")])
def test_scheduler_changes_are_detected_across_observation(field, value):
    def change(name, round_number, data):
        if name == "scheduler" and round_number > 1:
            data[field] = value
        return data

    startup, _, clock = setup_startup(change=change)
    with pytest.raises(readiness.ReadinessError, match="scheduler: restarted or replaced"):
        startup.start()
    assert clock.waits == [1]


@pytest.mark.parametrize("waiting", ["migrate", "db", "web", "scheduler"])
def test_waiting_and_http_failures_obey_global_deadline(waiting):
    def change(name, round_number, data):
        if name == waiting:
            if name == "db":
                data[5] = "starting"
            elif name != "web":
                data[1] = "running" if name == "migrate" else "created"
        return data

    startup, _, clock = setup_startup(change=change, http=lambda n: 75 if waiting == "web" else 0)
    with pytest.raises(readiness.ReadinessError, match="deadline exceeded") as error:
        startup.start()
    assert error.value.code == 124
    assert clock.value == 12
    assert sum(clock.waits) == 12


@pytest.mark.parametrize("service", ["db", "migrate", "web", "scheduler"])
def test_missing_service_is_failure(service):
    startup, _, _ = setup_startup(change=lambda name, n, data: None if name == service else data)
    with pytest.raises(readiness.ReadinessError, match=service + ": container missing"):
        startup.start()


@pytest.mark.parametrize("field,value", [(0, "not-an-id"), (1, "private-payload"), (2, "bad"), (3, -1), (4, ""), (5, "bad")])
def test_invalid_state_is_not_readiness(field, value):
    def change(name, n, data):
        if name == "db":
            data[field] = value
        return data

    startup, _, _ = setup_startup(change=change)
    with pytest.raises(readiness.ReadinessError) as error:
        startup.start()
    assert "private-payload" not in str(error.value)


@pytest.mark.parametrize("stage", ["up", "ps", "inspect", "exec"])
def test_command_hangs_are_bounded_and_not_reported_as_success(stage):
    def fail(argv):
        if argv[2] == stage or argv[1] == stage:
            return subprocess.TimeoutExpired(argv, 1, output="private-payload")

    startup, docker, _ = setup_startup(fail=fail)
    with pytest.raises(readiness.ReadinessError, match="timed out") as error:
        startup.start()
    assert error.value.code == 124
    assert "private-payload" not in str(error.value)
    assert all(call[0][1:] != ["compose", "down"] for call in docker.calls)
    if stage == "up":
        assert len(docker.calls) == 1


def test_up_itself_consumes_the_startup_deadline():
    def consume(argv, clock):
        if argv[1:3] == ["compose", "up"]:
            clock.value += 12

    startup, docker, _ = setup_startup(consume=consume)
    with pytest.raises(readiness.ReadinessError, match="up: startup deadline exceeded"):
        startup.start()
    assert len(docker.calls) == 1


def test_probe_latency_cannot_return_success_after_deadline():
    def consume(argv, clock):
        if argv[1] == "exec":
            clock.value += 12

    startup, _, _ = setup_startup(consume=consume)
    with pytest.raises(readiness.ReadinessError, match="web HTTP: startup deadline exceeded"):
        startup.start()


@pytest.mark.parametrize("failure", [OSError("private-payload"), UnicodeDecodeError("utf-8", b"private-payload\xff", 0, 1, "bad")])
def test_state_command_exceptions_are_safe_and_fail_closed(failure):
    startup, _, _ = setup_startup(fail=lambda argv: failure if argv[1:3] == ["compose", "ps"] else None)
    with pytest.raises(readiness.ReadinessError) as error:
        startup.start()
    assert "private-payload" not in str(error.value)


@pytest.mark.parametrize("state", ["restarting", "exited", "dead", "paused"])
def test_scheduler_non_running_state_after_first_observation_is_failure(state):
    def change(name, round_number, data):
        if name == "scheduler" and round_number > 1:
            data[1] = state
        return data

    startup, _, _ = setup_startup(change=change)
    with pytest.raises(readiness.ReadinessError, match="scheduler: stopped or restarting"):
        startup.start()


@pytest.mark.parametrize("service", ["migrate", "db", "web"])
def test_up_failure_retains_exit_code_and_reports_dependency_cause(service):
    def change(name, n, data):
        if name == service:
            if service == "db":
                data[5] = "unhealthy"
            else:
                data[1], data[2] = "exited", 7
        return data

    startup, docker, _ = setup_startup(
        change=change, fail=lambda argv: 45 if argv[1:3] == ["compose", "up"] else None,
    )
    with pytest.raises(readiness.ReadinessError, match="up: " + service) as error:
        startup.start()
    assert error.value.code == 45
    assert all(call[0][1:] != ["compose", "down"] for call in docker.calls)


@pytest.mark.parametrize("kind", ["query-failure", "deadline"])
def test_failed_up_diagnostics_never_mask_original_failure(kind):
    def fail(argv):
        return 45 if argv[1:3] == ["compose", "up"] else 46 if kind == "query-failure" else None

    def consume(argv, clock):
        if kind == "deadline":
            clock.value += 11.9 if argv[1:3] == ["compose", "up"] else 0.2

    startup, _, _ = setup_startup(fail=fail, consume=consume)
    with pytest.raises(readiness.ReadinessError, match="up:") as error:
        startup.start()
    assert error.value.code == 45


@pytest.mark.parametrize("code,expected", [(45, 45), (-9, 137)])
def test_up_failure_preserves_shell_exit_semantics(code, expected):
    startup, _, _ = setup_startup(fail=lambda argv: code if argv[1:3] == ["compose", "up"] else None)
    with pytest.raises(readiness.ReadinessError) as error:
        startup.start()
    assert error.value.code == expected


def test_up_failure_can_diagnose_db_before_migration_container_exists():
    def change(name, n, data):
        if name == "migrate":
            return None
        if name == "db":
            data[5] = "unhealthy"
        return data

    startup, docker, _ = setup_startup(change=change, fail=lambda argv: 45 if argv[1:3] == ["compose", "up"] else None)
    with pytest.raises(readiness.ReadinessError, match="up: db") as error:
        startup.start()
    assert error.value.code == 45
    assert [argv[-1] for argv, _ in docker.calls if argv[1:3] == ["compose", "ps"]] == ["migrate", "db"]


def test_native_command_timeout_reaps_a_virtual_process():
    with pytest.raises(subprocess.TimeoutExpired):
        readiness.run_command([sys.executable, "-B", "-c", "import signal; signal.alarm(1); signal.pause()"], 0.05)


def test_restart_down_and_up_share_one_deadline():
    def consume(argv, clock):
        if argv[1:3] == ["compose", "down"]:
            clock.value += 5

    startup, docker, _ = setup_startup(consume=consume)
    startup.start(restart=True)
    assert docker.calls[0][0] == ["docker", "compose", "down"]
    assert docker.calls[0][1] == 12
    assert docker.calls[1][1] == 7


@pytest.mark.parametrize("key", ["TIMEOUT", "POLL", "STABLE", "COMMAND_TIMEOUT"])
@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "", " 2 ", "private-payload"])
def test_duration_inputs_are_strict_and_redacted(key, value):
    with pytest.raises(readiness.ReadinessError) as error:
        readiness.Options.from_env({"INVEST_BOT_START_" + key + "_SECONDS": value})
    assert "private-payload" not in str(error.value)


@pytest.mark.parametrize("env", [
    {"INVEST_BOT_START_TIMEOUT_SECONDS": "10"},
    {"INVEST_BOT_START_POLL_SECONDS": "11"},
    {"INVEST_BOT_START_COMMAND_TIMEOUT_SECONDS": "181"},
])
def test_invalid_duration_relationships_are_rejected(env):
    with pytest.raises(readiness.ReadinessError):
        readiness.Options.from_env(env)


def test_host_runtime_and_options_check_does_not_call_docker(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["readiness", "--check"])
    monkeypatch.setattr(readiness, "Startup", lambda *args: pytest.fail("check must not launch"))
    assert readiness.main() == 0
    monkeypatch.setattr(sys, "version_info", (3, 9))
    assert readiness.main() != 0


@pytest.mark.parametrize("host,port,base,ssl_cert", [
    ("0.0.0.0", "8012", "dashboard", None),
    ("::", "8000", "", None),
    ("127.0.0.1", "not-a-number", "/nested/path/", None),
    ("web.internal", "9000", "", "synthetic-cert"),
])
def test_http_probe_uses_container_bind_and_base_path_without_app_execution(monkeypatch, host, port, base, ssl_cert):
    from streamlit import config

    calls = []
    class Connection:
        def __init__(self, address, number, timeout):
            calls.append((address, number, timeout))
        def request(self, method, path):
            calls.append((method, path))
        def getresponse(self):
            return SimpleNamespace(status=200, read=lambda limit: b"ok")
        def close(self):
            calls.append("closed")

    monkeypatch.setenv("INVEST_BOT_DASHBOARD_HOST", host)
    monkeypatch.setenv("INVEST_BOT_DASHBOARD_PORT", port)
    monkeypatch.setattr(config, "get_option", lambda key: base if key == "server.baseUrlPath" else ssl_cert)
    monkeypatch.setattr(http.client, "HTTPConnection", Connection)
    monkeypatch.setattr(http.client, "HTTPSConnection", Connection)
    monkeypatch.setattr(sys, "argv", ["probe", "2"])
    with pytest.raises(SystemExit) as result:
        exec(readiness.HTTP_PROBE, {})
    assert result.value.code == 0
    assert calls[0] == ({"0.0.0.0": "127.0.0.1", "::": "::1"}.get(host, host), int(port) if port.isdigit() else 8000, 2.0)
    assert calls[1] == ("GET", "/" + (base.strip("/") + "/" if base.strip("/") else "") + "_stcore/health")
    assert calls[-1] == "closed"


@pytest.mark.parametrize("status,body", [(503, b"unavailable"), (404, b"ok"), (200, b"wrong")])
def test_http_status_and_body_are_required(monkeypatch, status, body):
    from streamlit import config

    monkeypatch.setattr(config, "get_option", lambda key: "")
    monkeypatch.setattr(sys, "argv", ["probe", "1"])
    monkeypatch.setattr(http.client, "HTTPConnection", lambda *args, **kwargs: SimpleNamespace(
        request=lambda *args: None, getresponse=lambda: SimpleNamespace(status=status, read=lambda n: body), close=lambda: None,
    ))
    with pytest.raises(SystemExit) as result:
        exec(readiness.HTTP_PROBE, {})
    assert result.value.code == 75


@pytest.mark.parametrize("name", ["start.sh", "restart.sh"])
@pytest.mark.parametrize("bad", ["runtime", "timeout"])
def test_preflight_rejects_invalid_runtime_or_options_before_docker(shell_project, name, bad):
    env = shell_project[3]
    if bad == "runtime":
        env["INVEST_BOT_PYTHON"] = "/missing/private-payload/python"
    else:
        env["INVEST_BOT_START_TIMEOUT_SECONDS"] = "private-payload"
    result, calls = _run_script(shell_project, name)
    assert result.returncode != 0
    assert calls == []
    assert "private-payload" not in result.stdout + result.stderr


@pytest.mark.parametrize("location", ["venv", "PATH"])
def test_runtime_fallback_runs_the_same_readiness_path(shell_project, location):
    project, _, _, env = shell_project
    runtime = env.pop("INVEST_BOT_PYTHON")
    if location == "venv":
        target = project / ".venv" / "bin" / "python"
    else:
        target = Path(runtime).parent / "python3"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(runtime, target)
    result, calls = _run_script(shell_project, "start.sh")
    assert result.returncode == 0, result.stderr
    assert "Service readiness confirmed" in result.stdout
    assert any(call["args"][0] == "exec" for call in calls)


@pytest.mark.parametrize("mode", ["migrate-failed", "db-unhealthy", "web-exit", "state-query", "migrate-absent-db-unhealthy"])
def test_real_helper_diagnoses_up_failure_in_shell_fixture(shell_project, mode):
    shell_project[3].update(FAKE_FAIL_STAGE="up", FAKE_EXIT_CODE="45", FAKE_READINESS_MODE=mode)
    result, calls = _run_script(shell_project, "start.sh")
    assert result.returncode == 45
    expected = {"migrate-failed": "migrate", "db-unhealthy": "db", "web-exit": "web", "state-query": "Docker command failed", "migrate-absent-db-unhealthy": "db"}
    assert "up: " + expected[mode] in result.stderr
    assert "private-payload" not in result.stdout + result.stderr
    assert not any(call["args"] == ["compose", "down"] for call in calls)


@pytest.mark.parametrize("name", ["start.sh", "restart.sh"])
@pytest.mark.parametrize("binary", ["true", "echo"])
def test_non_python_successful_executable_cannot_bypass_readiness(shell_project, name, binary):
    shell_project[3]["INVEST_BOT_PYTHON"] = shutil.which(binary, path="/usr/bin:/bin")
    result, calls = _run_script(shell_project, name)
    assert result.returncode != 0
    assert calls == []
    assert "runtime" in result.stderr.lower()


@pytest.mark.parametrize("host_value,file_value,public_port", [
    (None, None, 8000),
    ("8012", None, 8012),
    ("8012", "9900", 8012),
    (None, "9900", 9900),
    ("", "9900", 8000),
])
def test_compose_published_target_launcher_and_health_ports_align(
    monkeypatch, host_value, file_value, public_port,
):
    from scripts.run_streamlit_dashboard import build_streamlit_argv, resolve_dashboard_bind
    from streamlit import config

    key = "INVEST_BOT_DASHBOARD_PORT"
    web = yaml.safe_load((Path(__file__).resolve().parents[1] / "docker-compose.yml").read_text())["services"]["web"]
    # Synthetic .env only: host environment wins interpolation, then service
    # environment overrides env_file for the container. No real .env is read.
    env_file = {key: file_value} if file_value is not None else {}
    host_env = {key: host_value} if host_value is not None else {}
    interpolation = {**env_file, **host_env}

    def resolve(value):
        result = re.sub(
            r"\$\{([A-Z_][A-Z_0-9]*):-([^}]+)\}",
            lambda match: interpolation.get(match[1]) or match[2], str(value),
        )
        assert "${" not in result
        return result

    published, target = map(int, resolve(web["ports"][0]).split(":"))
    assert published == public_port
    container_env = {**env_file, **{name: resolve(value) for name, value in web["environment"].items()}}
    with monkeypatch.context() as local:
        local.delenv("INVEST_BOT_DASHBOARD_HOST", raising=False)
        local.delenv(key, raising=False)
        if host_value:
            local.setenv(key, host_value)
        _, local_port = resolve_dashboard_bind()
        assert local_port == (int(host_value) if host_value else 8000)

    monkeypatch.setenv(key, container_env[key])
    monkeypatch.setenv("INVEST_BOT_DASHBOARD_HOST", container_env["INVEST_BOT_DASHBOARD_HOST"])
    host, bind_port = resolve_dashboard_bind()
    argv = build_streamlit_argv(host, bind_port)
    assert bind_port == target
    assert int(argv[argv.index("--server.port") + 1]) == target

    probe_connections = []
    monkeypatch.setattr(config, "get_option", lambda name: "")
    monkeypatch.setattr(sys, "argv", ["probe", "1"])
    def connection(address, port, timeout):
        probe_connections.append((address, port))
        return SimpleNamespace(
            request=lambda *args: None,
            getresponse=lambda: SimpleNamespace(status=200, read=lambda n: b"ok"),
            close=lambda: None,
        )
    monkeypatch.setattr(http.client, "HTTPConnection", connection)
    with pytest.raises(SystemExit) as result:
        exec(readiness.HTTP_PROBE, {})
    assert result.value.code == 0
    assert probe_connections == [("127.0.0.1", target)]
