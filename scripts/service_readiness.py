"""Bound Compose startup and verify process readiness without running application jobs."""
from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass


INSPECT_FORMAT = (
    "{{.Id}}|{{.State.Status}}|{{.State.ExitCode}}|{{.RestartCount}}|"
    "{{.State.StartedAt}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}"
)
CHECK_RESPONSE = "invest-bot-readiness-check-v1"
# Executed inside the selected web container. No app entry point or job is imported.
HTTP_PROBE = """
import http.client
import os
import sys
from urllib.parse import quote

try:
    from streamlit import config
    host = os.getenv('INVEST_BOT_DASHBOARD_HOST', '127.0.0.1').strip() or '127.0.0.1'
    host = {'0.0.0.0': '127.0.0.1', '::': '::1', '[::]': '::1'}.get(host, host)
    try:
        port = int(os.getenv('INVEST_BOT_DASHBOARD_PORT', '8000').strip())
    except ValueError:
        port = 8000
    if not 1 <= port <= 65535:
        raise ValueError('invalid bind')
    base = config.get_option('server.baseUrlPath') or ''
    path = '/' + (quote(base.strip('/'), safe='/') + '/' if base.strip('/') else '') + '_stcore/health'
    connection_type = http.client.HTTPSConnection if config.get_option('server.sslCertFile') else http.client.HTTPConnection
    connection = connection_type(host, port, timeout=float(sys.argv[1]))
except Exception:
    sys.exit(70)
try:
    connection.request('GET', path)
    response = connection.getresponse()
    ready = response.status == 200 and response.read(16) == b'ok'
except (OSError, http.client.HTTPException):
    ready = False
finally:
    connection.close()
sys.exit(0 if ready else 75)
"""


class ReadinessError(Exception):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


class ContainerMissing(ReadinessError):
    pass


@dataclass(frozen=True)
class Options:
    timeout: float = 180
    poll: float = 1
    stable: float = 10
    command_timeout: float = 5

    @classmethod
    def from_env(cls, env):
        values = []
        for suffix, default in (("TIMEOUT", "180"), ("POLL", "1"), ("STABLE", "10"), ("COMMAND_TIMEOUT", "5")):
            key = "INVEST_BOT_START_" + suffix + "_SECONDS"
            raw = env.get(key, default)
            if not re.fullmatch(r"(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)", raw):
                raise ReadinessError("options: invalid " + key)
            value = float(raw)
            if not 0 < value <= 86400:
                raise ReadinessError("options: invalid " + key)
            values.append(value)
        options = cls(*values)
        if not options.poll <= options.stable < options.timeout or options.command_timeout > options.timeout:
            raise ReadinessError("options: require poll <= stability < timeout and command cap <= timeout")
        return options


def run_command(argv, timeout):
    """Kill only this CLI process group on timeout/control exit; never run cleanup Docker commands."""
    process = subprocess.Popen(
        argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, start_new_session=True,
    )
    try:
        stdout, _ = process.communicate(timeout=timeout)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            process.communicate(timeout=0.2)
        except subprocess.TimeoutExpired:
            process.stdout.close()
            try:
                process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                pass
        raise
    return subprocess.CompletedProcess(argv, process.returncode, stdout=stdout)


class Startup:
    def __init__(self, options, *, execute=run_command, clock=time.monotonic, sleep=time.sleep):
        self.options = options
        self.execute = execute
        self.clock = clock
        self.sleep = sleep
        self.deadline = 0.0

    def remaining(self, stage):
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            raise ReadinessError(stage + ": startup deadline exceeded", 124)
        return remaining

    def command(self, stage, argv, *, allowed=(), full_budget=False):
        remaining = self.remaining(stage)
        timeout = remaining if full_budget else min(self.options.command_timeout, remaining)
        try:
            result = self.execute(argv, timeout)
        except subprocess.TimeoutExpired:
            raise ReadinessError(stage + ": Docker command timed out", 124) from None
        except OSError:
            raise ReadinessError(stage + ": Docker command unavailable") from None
        except UnicodeError:
            raise ReadinessError(stage + ": invalid command response") from None
        self.remaining(stage)
        if result.returncode and result.returncode not in allowed:
            code = result.returncode if result.returncode > 0 else 128 - result.returncode
            raise ReadinessError(stage + ": Docker command failed", code)
        return result

    def inspect(self, service):
        ids = self.command(service + " state", ["docker", "compose", "ps", "--all", "--quiet", service]).stdout.split()
        if not ids:
            raise ContainerMissing(service + ": container missing")
        if len(ids) != 1 or not re.fullmatch(r"[a-f0-9]{12,64}", ids[0]):
            raise ReadinessError(service + ": ambiguous or invalid container ID")
        output = self.command(
            service + " inspect", ["docker", "inspect", "--type", "container", "--format", INSPECT_FORMAT, ids[0]],
        ).stdout.strip().split("|")
        if len(output) != 6:
            raise ReadinessError(service + ": invalid state response")
        identity, state, exit_code, restarts, started, health = output
        if (not re.fullmatch(r"[a-f0-9]{64}", identity) or not identity.startswith(ids[0])
                or state not in {"created", "running", "restarting", "exited", "dead", "paused", "removing"}
                or not re.fullmatch(r"[0-9]+", exit_code) or not re.fullmatch(r"[0-9]+", restarts)
                or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,9})?Z", started)
                or health not in {"healthy", "starting", "unhealthy", "none"}):
            raise ReadinessError(service + ": invalid state response")
        return identity, state, int(exit_code), int(restarts), started, health

    def start(self, *, restart=False):
        self.deadline = self.clock() + self.options.timeout
        if restart:
            self.command("down", ["docker", "compose", "down"], full_budget=True)
        try:
            self.command("up", ["docker", "compose", "up", "-d", "db", "migrate", "scheduler", "web"], full_budget=True)
        except ReadinessError as error:
            if error.code == 124:
                raise
            raise self.diagnose_up_failure(error) from None
        markers = {}
        stable_since = None
        samples = 0
        waiting_for = "services"
        while True:
            self.remaining(waiting_for)
            states = {service: self.inspect(service) for service in ("db", "migrate", "web", "scheduler")}
            ready = True
            for service, (identity, state, exit_code, restarts, started, health) in states.items():
                if service == "migrate":
                    if state == "exited" and exit_code == 0:
                        continue
                    if state not in {"created", "running"}:
                        raise ReadinessError("migrate: unsuccessful terminal state")
                    ready, waiting_for = False, "migrate"
                    continue
                if state not in {"created", "running"}:
                    raise ReadinessError(service + ": stopped or restarting")
                if state == "created":
                    ready, waiting_for = False, service
                    continue
                marker = identity, started, restarts
                if service in markers and markers[service] != marker:
                    raise ReadinessError(service + ": restarted or replaced during observation")
                markers[service] = marker
                if service == "db" and health != "healthy":
                    if health in {"unhealthy", "none"}:
                        raise ReadinessError("db: health check failed or missing")
                    ready, waiting_for = False, "db health"
            if states["scheduler"][1] == "running":
                if stable_since is None:
                    stable_since = self.clock()
                samples += 1
            web_ready = False
            if states["web"][1] == "running":
                probe_timeout = min(self.options.command_timeout, self.remaining("web HTTP"))
                probe = self.command(
                    "web HTTP", ["docker", "exec", states["web"][0], "python", "-I", "-B", "-c", HTTP_PROBE, str(probe_timeout)],
                    allowed=(75,),
                )
                web_ready = probe.returncode == 0
                if not web_ready:
                    waiting_for = "web HTTP"
            stable = stable_since is not None and samples >= 2 and self.clock() - stable_since >= self.options.stable
            self.remaining(waiting_for)
            if ready and web_ready and stable:
                return
            if ready and web_ready:
                waiting_for = "scheduler stability"
            self.sleep(min(self.options.poll, self.remaining(waiting_for)))

    def diagnose_up_failure(self, original):
        # Dependents may never start when Compose fails while waiting for migration.
        # No extra deadline and no raw daemon error/log output for diagnostics.
        for service in ("migrate", "db", "web"):
            try:
                _, state, code, _, _, health = self.inspect(service)
            except ContainerMissing:
                continue
            except ReadinessError:
                return original
            if service == "migrate" and state not in {"created", "running"} and (state != "exited" or code != 0):
                return ReadinessError("up: migrate unsuccessful terminal state", original.code)
            if service == "db" and (state not in {"created", "running"} or health == "unhealthy"):
                return ReadinessError("up: db health check failed", original.code)
            if service == "web" and state not in {"created", "running"}:
                return ReadinessError("up: web stopped or restarting", original.code)
        return original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate host runtime and readiness options without Docker.")
    parser.add_argument("--restart", action="store_true", help="Run bounded down before bounded up and readiness checks.")
    args = parser.parse_args()
    try:
        if sys.version_info < (3, 10) or os.name != "posix":
            raise ReadinessError("runtime: POSIX Python 3.10 or newer is required")
        options = Options.from_env(os.environ)
        if args.check:
            print(CHECK_RESPONSE)
        else:
            Startup(options).start(restart=args.restart)
            print("Service readiness confirmed (internal HTTP and process stability).")
    except ReadinessError as error:
        print("Readiness failed: " + str(error), file=sys.stderr)
        return error.code
    except KeyboardInterrupt:
        print("Readiness failed: interrupted", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
