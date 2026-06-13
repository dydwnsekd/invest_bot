from __future__ import annotations

from invest_bot.config.settings import AppSettings
from invest_bot.db.metadata import Base
import invest_bot.db.models  # noqa: F401


MANAGED_TABLES = frozenset(Base.metadata.tables.keys())


def build_database_url(settings: AppSettings | None = None) -> str:
    resolved = settings or AppSettings.from_file()
    return resolved.database_url


def should_stamp_existing_schema(existing_tables: set[str], *, has_version_table: bool) -> bool:
    if has_version_table:
        return False
    return bool(MANAGED_TABLES) and MANAGED_TABLES.issubset(existing_tables)


__all__ = ["Base", "MANAGED_TABLES", "build_database_url", "should_stamp_existing_schema"]
