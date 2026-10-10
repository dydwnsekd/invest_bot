from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers import sanitized_subprocess_environment


ROOT = Path(__file__).resolve().parents[1]
VALIDATE_COMMAND = [
    "compose", "run", "--rm", "--no-deps", "scheduler",
    "python", "scripts/run_scheduled_collection.py", "--validate-config",
]
COMMANDS = {
    "config": ["compose", "config", "--quiet"],
    "build": ["compose", "build"],
    "validate": VALIDATE_COMMAND,
    "down": ["compose", "down"],
    "up": ["compose", "up", "-d", "db", "migrate", "scheduler", "web"],
}


@pytest.fixture
def shell_project(tmp_path):
    project = tmp_path / "project with spaces"
    project.mkdir()
    for name in ("start.sh", "restart.sh", "stop.sh"):
        shutil.copy2(ROOT / name, project / name)
    config_dir = project / "config"
    config_dir.mkdir()
    (config_dir / "collection_schedule.yaml").write_text(
        "symbols: ['005930']\nrun_on_startup: false\n", encoding="utf-8"
    )
    fake_bin = tmp_path / "fake bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text(
        f"""#!{sys.executable}
import json
import os
import subprocess
import sys
from pathlib import Path

args = sys.argv[1:]
with open(os.environ["FAKE_DOCKER_LOG"], "a", encoding="utf-8") as output:
    output.write(json.dumps({{"cwd": os.getcwd(), "args": args}}) + "\\n")
stage = {{
    "config": "config",
    "build": "build",
    "run": "validate",
    "down": "down",
    "up": "up",
    "stop": "stop",
}}.get(args[1] if len(args) > 1 else "", "unknown")
if stage == os.environ.get("FAKE_FAIL_STAGE"):
    sys.exit(int(os.environ["FAKE_EXIT_CODE"]))
if stage == "validate":
    sys.exit(subprocess.run(
        [sys.executable, os.environ["FAKE_SCHEDULER_SCRIPT"], "--validate-config",
         "--config", str(Path.cwd() / "config" / "collection_schedule.yaml")],
        env=os.environ,
    ).returncode)
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    external_cwd = tmp_path / "external directory"
    external_cwd.mkdir()
    log = tmp_path / "docker_calls.jsonl"
    env = sanitized_subprocess_environment()
    env.update({
        "PATH": os.pathsep.join((str(fake_bin), "/usr/bin", "/bin")),
        "PYTHONPATH": str(ROOT / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "FAKE_DOCKER_LOG": str(log),
        "FAKE_SCHEDULER_SCRIPT": str(ROOT / "scripts" / "run_scheduled_collection.py"),
    })
    return project, external_cwd, log, env


def _run_script(shell_project, name):
    project, external_cwd, log, env = shell_project
    result = subprocess.run(
        ["bash", str(project / name)],
        cwd=external_cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return result, calls


@pytest.mark.parametrize("name", ["start.sh", "restart.sh"])
def test_start_and_restart_validate_before_service_changes(shell_project, name):
    project, _, _, _ = shell_project
    result, calls = _run_script(shell_project, name)
    stages = ["config", "build", "validate"]
    if name == "restart.sh":
        stages.append("down")
    stages.append("up")

    assert result.returncode == 0, result.stderr
    assert [call["args"] for call in calls] == [COMMANDS[stage] for stage in stages]
    assert all(call["cwd"] == str(project) for call in calls)


@pytest.mark.parametrize("name", ["start.sh", "restart.sh"])
def test_missing_schedule_exits_before_any_docker_call(shell_project, name):
    project, _, _, _ = shell_project
    (project / "config" / "collection_schedule.yaml").unlink()

    result, calls = _run_script(shell_project, name)

    assert result.returncode != 0
    assert "Missing config/collection_schedule.yaml" in result.stderr
    assert calls == []


@pytest.mark.parametrize("name", ["start.sh", "restart.sh"])
@pytest.mark.parametrize("stage,code", [("config", 31), ("build", 42), ("validate", 43), ("up", 45)])
def test_docker_failure_exit_code_is_propagated(shell_project, name, stage, code):
    shell_project[3].update({"FAKE_FAIL_STAGE": stage, "FAKE_EXIT_CODE": str(code)})

    result, calls = _run_script(shell_project, name)

    stages = ["config", "build", "validate"]
    if name == "restart.sh":
        stages.append("down")
    stages.append("up")
    expected = stages[:stages.index(stage) + 1]
    assert result.returncode == code
    assert [call["args"] for call in calls] == [COMMANDS[item] for item in expected]


def test_failed_down_does_not_call_up(shell_project):
    shell_project[3].update({"FAKE_FAIL_STAGE": "down", "FAKE_EXIT_CODE": "44"})

    result, calls = _run_script(shell_project, "restart.sh")

    assert result.returncode == 44
    assert [call["args"] for call in calls] == [
        COMMANDS[item] for item in ("config", "build", "validate", "down")
    ]


@pytest.mark.parametrize("name", ["start.sh", "restart.sh"])
@pytest.mark.parametrize("text", [
    "symbols: [\nextra: private-payload\n",
    "symbols: []\n",
    "symbols: ['005930']\ninterval_minutes: private-payload\n",
])
def test_real_invalid_config_validation_prevents_down_and_up(shell_project, name, text):
    project, _, _, _ = shell_project
    (project / "config" / "collection_schedule.yaml").write_text(text, encoding="utf-8")

    result, calls = _run_script(shell_project, name)

    assert result.returncode != 0
    assert [call["args"] for call in calls] == [
        COMMANDS[item] for item in ("config", "build", "validate")
    ]
    assert "private-payload" not in result.stdout + result.stderr


def test_stop_keeps_existing_stop_contract(shell_project):
    project, _, _, _ = shell_project

    result, calls = _run_script(shell_project, "stop.sh")

    assert result.returncode == 0
    assert calls == [{"cwd": str(project), "args": ["compose", "stop"]}]
