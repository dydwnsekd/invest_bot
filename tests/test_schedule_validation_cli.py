from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers import sanitized_subprocess_environment


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def validation_environment(tmp_path):
    bootstrap = tmp_path / "bootstrap"
    bootstrap.mkdir()
    audit = tmp_path / "unexpected_calls.jsonl"
    (bootstrap / "sitecustomize.py").write_text(
        """
import json
import os
import socket
import urllib.request
from pathlib import Path

def blocked(kind):
    def fail(*args, **kwargs):
        with open(os.environ["VALIDATION_AUDIT"], "a") as output:
            output.write(json.dumps(kind) + "\\n")
        raise AssertionError("unexpected runtime call: " + kind)
    return fail

socket.socket.connect = blocked("network")
urllib.request.urlopen = blocked("urlopen")
import sqlalchemy
sqlalchemy.create_engine = blocked("database")
from invest_bot.config.settings import AppSettings
AppSettings.from_file = blocked("app settings")
import invest_bot.db.engine as engine
engine.build_engine = blocked("database")
import invest_bot.market.master_sync as master_sync
master_sync.sync_stock_master = blocked("master sync")
import invest_bot.jobs.collect_market_data as collect_job
collect_job.collect_market_data_for_symbols = blocked("collector")
import invest_bot.jobs.scheduled_collection as schedule
schedule.ScheduledCollectionRunner.__init__ = blocked("runner")
Path(os.environ["VALIDATION_READY"]).touch()
""",
        encoding="utf-8",
    )
    env = sanitized_subprocess_environment()
    env.update({
        "PYTHONPATH": os.pathsep.join((str(bootstrap), str(ROOT / "src"))),
        "PYTHONDONTWRITEBYTECODE": "1",
        "VALIDATION_AUDIT": str(audit),
        "VALIDATION_READY": str(tmp_path / "guards_ready"),
    })
    return env, audit


@pytest.mark.parametrize("text,valid", [
    ("symbols: ['005930']\nrun_on_startup: 'false'\n", True),
    ("symbols: [\nsecret: private-payload\n", False),
    ("symbols: ['005930']\ninterval_minutes: private-payload\n", False),
    ("symbols: ['005930']\nsymbols_file: private-payload\n", False),
    ("symbols: []\n", False),
])
def test_true_validation_cli_has_no_runtime_side_effects(tmp_path, validation_environment, text, valid):
    env, audit = validation_environment
    log = tmp_path / "runtime" / "collection.log"
    config = tmp_path / "schedule.yaml"
    config.write_text(text + f"log_path: {log.as_posix()}\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_scheduled_collection.py"),
         "--config", str(config), "--validate-config"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert (result.returncode == 0) == valid, result.stderr
    if valid:
        assert "Collection schedule configuration is valid." in result.stdout
    else:
        assert "Invalid collection schedule" in result.stderr
    assert "private-payload" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert "Error in sitecustomize" not in result.stderr
    assert Path(env["VALIDATION_READY"]).exists()
    assert not audit.exists()
    assert not log.parent.exists()


def test_validation_cli_reports_missing_config_without_runtime_calls(tmp_path, validation_environment):
    env, audit = validation_environment
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_scheduled_collection.py"),
         "--config", str(tmp_path / "missing.yaml"), "--validate-config"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode != 0
    assert "Invalid collection schedule" in result.stderr
    assert "Traceback" not in result.stderr
    assert "Error in sitecustomize" not in result.stderr
    assert Path(env["VALIDATION_READY"]).exists()
    assert not audit.exists()
