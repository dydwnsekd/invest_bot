from __future__ import annotations

import os
from urllib.parse import quote_plus

from invest_bot.db.metadata import Base


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


__all__ = ["Base", "build_database_url"]
