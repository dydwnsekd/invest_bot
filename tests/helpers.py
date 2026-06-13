from __future__ import annotations

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
