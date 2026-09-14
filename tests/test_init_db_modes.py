from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_init_db_module():
    spec = importlib.util.spec_from_file_location("init_db_script", ROOT / "scripts" / "init_db.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_only_mode_never_calls_stock_master(monkeypatch, capsys):
    module = _load_init_db_module()
    calls: list[str] = []
    monkeypatch.setattr(module, "migrate", lambda: calls.append("migrate"))
    monkeypatch.setattr(module, "sync_stock_master", lambda **kwargs: calls.append("sync"))

    module.main(["--mode", "migrate-only"])

    assert calls == ["migrate"]
    assert capsys.readouterr().out.splitlines() == [
        "database migration complete",
        "stock master sync skipped (migration-only mode)",
    ]


def test_default_mode_preserves_full_initialization(monkeypatch, capsys):
    module = _load_init_db_module()
    calls: list[object] = []
    monkeypatch.delenv("INVEST_BOT_INIT_MODE", raising=False)
    monkeypatch.setattr(module, "migrate", lambda: calls.append("migrate"))
    monkeypatch.setattr(module, "sync_stock_master", lambda **kwargs: calls.append(kwargs))

    module.main([])

    assert calls == ["migrate", {"force_refresh": True}]
    assert "database initialization complete" in capsys.readouterr().out


def test_environment_selects_migration_only_mode(monkeypatch):
    module = _load_init_db_module()
    calls: list[str] = []
    monkeypatch.setenv("INVEST_BOT_INIT_MODE", "migrate-only")
    monkeypatch.setattr(module, "migrate", lambda: calls.append("migrate"))
    monkeypatch.setattr(module, "sync_stock_master", lambda **kwargs: calls.append("sync"))

    module.main([])

    assert calls == ["migrate"]


def test_invalid_environment_mode_fails_before_migration(monkeypatch):
    module = _load_init_db_module()
    calls: list[str] = []
    monkeypatch.setenv("INVEST_BOT_INIT_MODE", "migration-only")
    monkeypatch.setattr(module, "migrate", lambda: calls.append("migrate"))

    with pytest.raises(SystemExit) as exc_info:
        module.main([])

    assert exc_info.value.code == 2
    assert calls == []


def test_cli_mode_overrides_environment(monkeypatch):
    module = _load_init_db_module()
    calls: list[str] = []
    monkeypatch.setenv("INVEST_BOT_INIT_MODE", "full")
    monkeypatch.setattr(module, "migrate", lambda: calls.append("migrate"))
    monkeypatch.setattr(module, "sync_stock_master", lambda **kwargs: calls.append("sync"))

    module.main(["--mode", "migrate-only"])

    assert calls == ["migrate"]
