from __future__ import annotations

from pathlib import Path
from uuid import uuid4


def make_test_dir(name: str) -> Path:
    root = Path(".tmp") / "test_artifacts" / name / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root
