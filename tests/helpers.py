from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from invest_bot.db.engine import build_engine, ensure_schema


def make_test_dir(name: str) -> Path:
    root = Path(".tmp") / "test_artifacts" / name / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


def init_test_db(database_url: str) -> None:
    engine = build_engine(database_url)
    try:
        ensure_schema(engine)
    finally:
        engine.dispose()


def sanitized_subprocess_environment() -> dict[str, str]:
    """Copy the process environment without invest_bot runtime credentials or DB targets."""
    blocked_names = {"DATABASE_URL", "DISCORD_WEBHOOK_URL"}
    return {
        key: value
        for key, value in os.environ.items()
        if key not in blocked_names and not key.startswith("INVEST_BOT_")
    }
