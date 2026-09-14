from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect, text

from invest_bot.db.migrate_runtime import build_alembic_config, migrate
from invest_bot.db.migration import INITIAL_SCHEMA_REVISION


def _tables_and_revision(database_url: str) -> tuple[set[str], str]:
    engine = create_engine(database_url, future=True)
    try:
        tables = set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        return tables, revision
    finally:
        engine.dispose()


def test_fresh_sqlite_migration_reaches_report_favorites_head(tmp_path, monkeypatch):
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'fresh.db').as_posix()}"
    monkeypatch.setenv("INVEST_BOT_DATABASE_URL", database_url)

    command.upgrade(build_alembic_config(), "head")

    tables, revision = _tables_and_revision(database_url)
    assert "report_favorite_symbols" in tables
    assert revision == "20260703_000003"


def test_legacy_initial_sqlite_schema_is_stamped_and_upgraded(tmp_path, monkeypatch):
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    monkeypatch.setenv("INVEST_BOT_DATABASE_URL", database_url)
    config = build_alembic_config()
    command.upgrade(config, INITIAL_SCHEMA_REVISION)
    engine = create_engine(database_url, future=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))
    finally:
        engine.dispose()

    migrate()

    tables, revision = _tables_and_revision(database_url)
    assert "dataset_frames" in tables
    assert "report_favorite_symbols" in tables
    assert revision == "20260703_000003"
