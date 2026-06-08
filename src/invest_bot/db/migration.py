from __future__ import annotations

import os
from urllib.parse import quote_plus

from invest_bot.db.metadata import Base
import invest_bot.db.models  # noqa: F401


MANAGED_TABLES = frozenset(Base.metadata.tables.keys())


def build_database_url() -> str:
    direct_url = os.getenv("DATABASE_URL", "").strip()
    if direct_url:
        return direct_url

    host = os.getenv("INVEST_BOT_DB_HOST", "127.0.0.1")
    port = os.getenv("INVEST_BOT_DB_PORT", "5432")
    name = os.getenv("INVEST_BOT_DB_NAME", "invest_bot")
    user = quote_plus(os.getenv("INVEST_BOT_DB_USER", "invest_bot"))
    password = quote_plus(os.getenv("INVEST_BOT_DB_PASSWORD", "invest_bot"))
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"


def should_stamp_existing_schema(existing_tables: set[str], *, has_version_table: bool) -> bool:
    if has_version_table:
        return False
    return bool(MANAGED_TABLES) and MANAGED_TABLES.issubset(existing_tables)


__all__ = ["Base", "MANAGED_TABLES", "build_database_url", "should_stamp_existing_schema"]
