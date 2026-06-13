from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_init_db_script_runs_migrations_for_sqlite(tmp_path) -> None:
    db_path = tmp_path / "init-script.db"
    config_dir = ROOT / "config"
    app_config = config_dir / "app.yaml"
    original = app_config.read_text(encoding="utf-8") if app_config.exists() else None
    app_config.write_text(f"database_url: sqlite+pysqlite:///{db_path.as_posix()}\n", encoding="utf-8")

    try:
        result = subprocess.run(
            [str(ROOT / ".venv" / "bin" / "python"), "scripts/init_db.py"],
            cwd=ROOT,
            env={"PYTHONPATH": str(ROOT / "src")},
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        if original is None:
            app_config.unlink(missing_ok=True)
        else:
            app_config.write_text(original, encoding="utf-8")

    assert "database initialization complete" in result.stdout
    assert db_path.exists()
