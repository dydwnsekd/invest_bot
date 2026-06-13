from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from invest_bot.db.migration import MANAGED_TABLES, build_database_url, should_stamp_existing_schema


def build_alembic_config() -> Config:
    project_root = Path(__file__).resolve().parents[3]
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "migrations"))
    config.set_main_option("sqlalchemy.url", build_database_url())
    return config


def migrate() -> None:
    database_url = build_database_url()
    engine = create_engine(database_url, future=True)
    inspector = inspect(engine)

    try:
        existing_tables = set(inspector.get_table_names())
        has_version_table = inspector.has_table("alembic_version")
    finally:
        engine.dispose()

    config = build_alembic_config()
    if should_stamp_existing_schema(existing_tables, has_version_table=has_version_table):
        print(
            "Existing bootstrap schema detected without alembic_version; "
            f"stamping head for tables: {', '.join(sorted(MANAGED_TABLES))}"
        )
        command.stamp(config, "head")

    command.upgrade(config, "head")


if __name__ == "__main__":
    migrate()
