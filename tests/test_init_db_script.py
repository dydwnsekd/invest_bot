from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run_init_db(database_url: str) -> subprocess.CompletedProcess[str]:
    config_dir = ROOT / "config"
    app_config = config_dir / "app.yaml"
    original = app_config.read_text(encoding="utf-8") if app_config.exists() else None
    app_config.write_text(f"database_url: {database_url}\n", encoding="utf-8")

    try:
        return subprocess.run(
            [str(ROOT / ".venv" / "bin" / "python"), "scripts/init_db.py"],
            cwd=ROOT,
            env={"PYTHONPATH": str(ROOT / "src")},
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        if original is None:
            app_config.unlink(missing_ok=True)
        else:
            app_config.write_text(original, encoding="utf-8")


def test_init_db_script_runs_migrations_for_sqlite(tmp_path) -> None:
    db_path = tmp_path / "init-script.db"

    result = _run_init_db(f"sqlite+pysqlite:///{db_path.as_posix()}")

    assert "database initialization complete" in result.stdout
    assert db_path.exists()


def test_init_db_script_upgrades_legacy_bootstrap_sqlite_db(tmp_path) -> None:
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

    result = _run_init_db(f"sqlite+pysqlite:///{db_path.as_posix()}")

    assert "database initialization complete" in result.stdout
    connection = sqlite3.connect(db_path)
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        versions = list(connection.execute("SELECT version_num FROM alembic_version"))
    finally:
        connection.close()

    assert "dataset_frames" in tables
    assert versions == [("20260612_000002",)]
