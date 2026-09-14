from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


RUNTIME_ENV_KEYS = {
    "DATABASE_URL",
    "DISCORD_WEBHOOK_URL",
    "INVEST_BOT_APP_NAME",
    "INVEST_BOT_APP_ROLE",
    "INVEST_BOT_DATABASE_URL",
    "INVEST_BOT_DB_HOST",
    "INVEST_BOT_DB_HOST_DOCKER",
    "INVEST_BOT_DB_NAME",
    "INVEST_BOT_DB_PASSWORD",
    "INVEST_BOT_DB_PORT",
    "INVEST_BOT_DB_USER",
    "INVEST_BOT_DISCORD_WEBHOOK_URL",
    "INVEST_BOT_ENABLE_DB_WRITE",
    "INVEST_BOT_ENVIRONMENT",
    "INVEST_BOT_INIT_MODE",
    "INVEST_BOT_KIS_APP_KEY",
    "INVEST_BOT_KIS_APP_SECRET",
    "INVEST_BOT_KIS_LIVE_APP_KEY",
    "INVEST_BOT_KIS_LIVE_APP_SECRET",
    "INVEST_BOT_KIS_MOCK_APP_KEY",
    "INVEST_BOT_KIS_MOCK_APP_SECRET",
    "INVEST_BOT_LOG_LEVEL",
    "INVEST_BOT_MARKET",
    "INVEST_BOT_STOCK_MASTER_REFRESH_INTERVAL_MINUTES",
    "INVEST_BOT_STOCK_MASTER_UPDATE_ON_STARTUP",
    "INVEST_BOT_TRADING_MODE",
}


@pytest.fixture(autouse=True)
def isolate_runtime_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent developer or CI runtime settings from leaking into unit tests."""
    for key in RUNTIME_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def block_external_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail fast when a default test attempts to use a real network socket."""
    if (
        request.node.get_closest_marker("external_network") is not None
        or request.node.get_closest_marker("postgresql") is not None
    ):
        return

    def blocked_connect(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError(
            "real network access is disabled in the default test suite; "
            "use a stub or mark an opt-in test with @pytest.mark.external_network"
        )

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)


@pytest.fixture
def synthetic_stock_master(tmp_path: Path) -> Path:
    """Return a deterministic local stock-master cache for isolated tests."""
    master_file = tmp_path / "stock_master.csv"
    master_file.write_text(
        "symbol,symbol_name,market\n005930,삼성전자,KOSPI\n000660,SK하이닉스,KOSPI\n",
        encoding="utf-8",
    )
    return master_file
