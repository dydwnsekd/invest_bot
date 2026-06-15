from __future__ import annotations

from invest_bot.config.settings import AppSettings
from invest_bot.db.metadata import Base
import invest_bot.db.models  # noqa: F401


INITIAL_SCHEMA_REVISION = "20260606_000001"
INITIAL_SCHEMA_TABLES = frozenset({"symbols", "daily_prices", "stock_info_snapshots", "investor_daily"})
MANAGED_TABLES = frozenset(Base.metadata.tables.keys())


def build_database_url(settings: AppSettings | None = None) -> str:
    resolved = settings or AppSettings.from_file()
    return resolved.database_url


def resolve_existing_schema_revision(existing_tables: set[str], *, has_version_table: bool) -> str | None:
    if has_version_table:
        return None
    if bool(MANAGED_TABLES) and MANAGED_TABLES.issubset(existing_tables):
        return "head"
    if INITIAL_SCHEMA_TABLES.issubset(existing_tables):
        return INITIAL_SCHEMA_REVISION
    return None


def should_stamp_existing_schema(existing_tables: set[str], *, has_version_table: bool) -> bool:
    return resolve_existing_schema_revision(existing_tables, has_version_table=has_version_table) is not None


__all__ = [
    "Base",
    "INITIAL_SCHEMA_REVISION",
    "INITIAL_SCHEMA_TABLES",
    "MANAGED_TABLES",
    "build_database_url",
    "resolve_existing_schema_revision",
    "should_stamp_existing_schema",
]
