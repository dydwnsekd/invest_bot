from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from invest_bot.jobs.scheduled_collection import CollectionScheduleConfig
from tests.test_operations_scripts import _run_script, shell_project
from tests.test_schedule_validation_cli import validation_environment


ROOT = Path(__file__).resolve().parents[1]


def _validate(config, cwd, validation_environment):
    env, audit = validation_environment
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_scheduled_collection.py"),
         "--validate-config", "--config", str(config)],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=15,
    )
    assert Path(env["VALIDATION_READY"]).exists()
    assert not audit.exists()
    assert "Error in sitecustomize" not in result.stderr
    assert "Traceback" not in result.stderr
    assert "qa-secret-value" not in result.stdout + result.stderr
    return result


@pytest.mark.parametrize("kind", ["config-directory", "symbols-directory", "symbols-utf8", "config-utf8"])
def test_validation_rejects_unreadable_paths_without_side_effects(tmp_path, validation_environment, kind):
    config = tmp_path / "schedule.yaml"
    log_path = tmp_path / "never-created" / "collection.log"
    config.write_text(f"symbols: ['005930']\nlog_path: {log_path}\n", encoding="utf-8")
    if kind == "config-directory":
        config = tmp_path / "config-directory"
        config.mkdir()
    elif kind == "config-utf8":
        config.write_bytes(b"symbols: ['005930']\nsecret: qa-secret-value\xff\n")
    else:
        symbols = tmp_path / "qa-secret-value"
        if kind == "symbols-directory":
            symbols.mkdir()
        else:
            symbols.write_bytes(b"005930\n\xffqa-secret-value\n")
        config.write_text(f"symbols_file: {symbols.name}\nlog_path: {log_path}\n", encoding="utf-8")

    result = _validate(config, tmp_path, validation_environment)
    assert result.returncode == 1
    assert "Invalid collection schedule" in result.stderr
    assert not log_path.parent.exists()


@pytest.mark.parametrize("project_valid", [True, False])
def test_default_validation_config_comes_from_project_not_external_cwd(
    tmp_path, validation_environment, project_valid,
):
    runtime = tmp_path / "validator project with spaces"
    shutil.copytree(ROOT / "src", runtime / "src")
    (runtime / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts/run_scheduled_collection.py", runtime / "scripts/run_scheduled_collection.py")
    (runtime / "config").mkdir()
    (runtime / "config/collection_schedule.yaml").write_text(
        "symbols: ['005930']\nrun_on_startup: 'false'\n" if project_valid else "symbols: []\n",
        encoding="utf-8",
    )
    external = tmp_path / "external cwd"
    (external / "config").mkdir(parents=True)
    (external / "config/collection_schedule.yaml").write_text(
        "symbols: []\n" if project_valid else "symbols: ['000660']\n", encoding="utf-8",
    )
    env, audit = validation_environment
    bootstrap = env["PYTHONPATH"].split(os.pathsep)[0]
    env["PYTHONPATH"] = os.pathsep.join((bootstrap, str(runtime / "src")))
    result = subprocess.run(
        [sys.executable, str(runtime / "scripts/run_scheduled_collection.py"), "--validate-config"],
        cwd=external, env=env, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == (0 if project_valid else 1), result.stderr
    assert Path(env["VALIDATION_READY"]).exists()
    assert not audit.exists()
    assert "Traceback" not in result.stderr
    assert "Error in sitecustomize" not in result.stderr
    assert not (runtime / ".runtime").exists()
    assert not (external / ".runtime").exists()


@pytest.mark.parametrize("name", ["start.sh", "restart.sh"])
@pytest.mark.parametrize("invalid", [
    {"symbols": {}},
    {"symbols": ["005930"], "days": True},
    {"symbols": ["005930"], "interval_minutes": 1.0},
    {"symbols": ["005930"], "days": 0},
    {"symbols": ["005930"], "days": -5},
    {"symbols": ["005930"], "symbols_file": "qa-secret-value"},
])
def test_invalid_schedule_stops_both_scripts_before_service_changes(shell_project, name, invalid):
    project = shell_project[0]
    payload = {**invalid, "kis_app_secret": "qa-secret-value"}
    (project / "config/collection_schedule.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")
    result, calls = _run_script(shell_project, name)
    assert result.returncode == 1
    assert [call["args"][1] for call in calls] == ["config", "build", "run"]
    assert "qa-secret-value" not in result.stdout + result.stderr
    assert not (project / ".runtime").exists()


@pytest.mark.parametrize("field", ["days", "interval_minutes"])
@pytest.mark.parametrize("value", ["+1", "-1", "1e3", "1_000", "１２", ".nan", "0.0", "  "])
def test_additional_non_decimal_numeric_forms_are_rejected(tmp_path, field, value):
    config = tmp_path / "schedule.yaml"
    config.write_text(yaml.safe_dump({"symbols": ["005930"], field: value}), encoding="utf-8")
    with pytest.raises(ValueError, match=field):
        CollectionScheduleConfig.from_file(config)


def test_symbols_file_only_and_string_false_preserve_defaults(tmp_path):
    (tmp_path / "symbols.txt").write_text("005930\n000660\n005930\n", encoding="utf-8")
    config = tmp_path / "schedule.yaml"
    config.write_text("symbols: null\nsymbols_file: symbols.txt\nrun_on_startup: 'false'\n", encoding="utf-8")
    schedule = CollectionScheduleConfig.from_file(config)
    assert schedule.symbols == ["005930", "000660"]
    assert schedule.run_on_startup is False
    assert (schedule.days, schedule.interval_minutes) == (365, 1440)
