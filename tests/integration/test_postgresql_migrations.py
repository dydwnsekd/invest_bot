from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from invest_bot.db.migrate_runtime import build_alembic_config


@pytest.mark.postgresql
def test_postgresql_migrations_upgrade_an_isolated_database(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = os.environ["QA_POSTGRESQL_URL"]
    parsed_url = make_url(database_url)
    assert parsed_url.get_backend_name() == "postgresql"
    assert parsed_url.host in {"127.0.0.1", "localhost", "postgres"}
    assert parsed_url.database is not None and parsed_url.database.endswith("_test")
    monkeypatch.setenv("INVEST_BOT_DATABASE_URL", database_url)

    config = build_alembic_config()
    command.upgrade(config, "head")

    engine = create_engine(database_url, future=True)
    try:
        tables = set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    finally:
        engine.dispose()

    assert {"symbols", "daily_prices", "stock_info_snapshots", "investor_daily", "dataset_frames"}.issubset(tables)
    expected_head = ScriptDirectory.from_config(config).get_current_head()
    assert revision == expected_head
    if expected_head == "20260703_000003":
        assert "report_favorite_symbols" in tables
