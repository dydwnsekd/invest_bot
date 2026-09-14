from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from tests.helpers import sanitized_subprocess_environment


ROOT = Path(__file__).resolve().parents[1]


def _run_init_db(database_url: str, tmp_path: Path, synthetic_stock_master: Path) -> subprocess.CompletedProcess[str]:
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        f"database_url: {database_url}\nenable_db_write: false\n",
        encoding="utf-8",
    )
    state_path = tmp_path / "stock_master_sync_state.json"
    bootstrap_dir = tmp_path / "python_bootstrap"
    bootstrap_dir.mkdir()
    (bootstrap_dir / "sitecustomize.py").write_text(
        "\n".join(
            [
                "import os",
                "import urllib.request",
                "from invest_bot.config.settings import AppSettings",
                "import invest_bot.market.master_sync as master_sync",
                "",
                "_settings_from_file = AppSettings.from_file.__func__",
                "def _from_test_config(cls, path=None):",
                "    return _settings_from_file(cls, os.environ['INVEST_BOT_TEST_CONFIG'])",
                "AppSettings.from_file = classmethod(_from_test_config)",
                "",
                "_master_repository = master_sync.StockMasterRepository",
                "master_sync.StockMasterRepository = lambda: _master_repository(",
                "    os.environ['INVEST_BOT_TEST_STOCK_MASTER']",
                ")",
                "_sync_init = master_sync.StockMasterSyncService.__init__",
                "def _isolated_sync_init(self, *args, state_file=None, **kwargs):",
                "    return _sync_init(",
                "        self, *args, state_file=state_file or os.environ['INVEST_BOT_TEST_SYNC_STATE'], **kwargs",
                "    )",
                "master_sync.StockMasterSyncService.__init__ = _isolated_sync_init",
                "",
                "def _blocked_urlopen(*args, **kwargs):",
                "    raise RuntimeError('network disabled by isolated init-db test')",
                "urllib.request.urlopen = _blocked_urlopen",
            ]
        ),
        encoding="utf-8",
    )

    env = sanitized_subprocess_environment()
    env.update(
        {
            "INVEST_BOT_TEST_CONFIG": str(config_path),
            "INVEST_BOT_TEST_STOCK_MASTER": str(synthetic_stock_master),
            "INVEST_BOT_TEST_SYNC_STATE": str(state_path),
            "PYTHONPATH": os.pathsep.join([str(bootstrap_dir), str(ROOT / "src")]),
        }
    )
    return subprocess.run(
        [sys.executable, "scripts/init_db.py"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _migration_head() -> str:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    return ScriptDirectory.from_config(config).get_current_head()


def test_init_db_script_runs_migrations_for_sqlite(tmp_path, synthetic_stock_master) -> None:
    db_path = tmp_path / "init-script.db"
    project_config = ROOT / "config" / "app.yaml"
    config_before = project_config.read_bytes() if project_config.exists() else None

    result = _run_init_db(f"sqlite+pysqlite:///{db_path.as_posix()}", tmp_path, synthetic_stock_master)

    assert "database initialization complete" in result.stdout
    assert db_path.exists()
    config_after = project_config.read_bytes() if project_config.exists() else None
    assert config_after == config_before


def test_init_db_script_upgrades_legacy_bootstrap_sqlite_db(tmp_path, synthetic_stock_master) -> None:
    db_path = tmp_path / "legacy-bootstrap.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE symbols (
                symbol TEXT PRIMARY KEY NOT NULL,
                symbol_name TEXT NOT NULL,
                market TEXT NOT NULL,
                is_active INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE daily_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                symbol TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                open_price NUMERIC,
                high_price NUMERIC,
                low_price NUMERIC,
                close_price NUMERIC,
                volume INTEGER,
                turnover NUMERIC,
                source_filename TEXT,
                collected_at TEXT NOT NULL,
                FOREIGN KEY(symbol) REFERENCES symbols(symbol) ON DELETE CASCADE,
                UNIQUE(symbol, trade_date)
            );
            CREATE TABLE stock_info_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                symbol TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                product_name TEXT,
                market_code TEXT,
                raw_payload TEXT,
                source_filename TEXT,
                FOREIGN KEY(symbol) REFERENCES symbols(symbol) ON DELETE CASCADE,
                UNIQUE(symbol, captured_at)
            );
            CREATE TABLE investor_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                symbol TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                foreign_net_qty NUMERIC,
                institutional_net_qty NUMERIC,
                personal_net_qty NUMERIC,
                raw_payload TEXT,
                source_filename TEXT,
                collected_at TEXT NOT NULL,
                FOREIGN KEY(symbol) REFERENCES symbols(symbol) ON DELETE CASCADE,
                UNIQUE(symbol, trade_date)
            );
            """
        )
        connection.commit()
    finally:
        connection.close()

    result = _run_init_db(f"sqlite+pysqlite:///{db_path.as_posix()}", tmp_path, synthetic_stock_master)

    assert "database initialization complete" in result.stdout
    connection = sqlite3.connect(db_path)
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        versions = list(connection.execute("SELECT version_num FROM alembic_version"))
    finally:
        connection.close()

    assert "dataset_frames" in tables
    assert versions == [(_migration_head(),)]
