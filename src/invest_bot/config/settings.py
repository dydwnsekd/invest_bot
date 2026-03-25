from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import os


class TradingMode(StrEnum):
    MOCK = "mock"
    LIVE = "live"


@dataclass(slots=True)
class AppSettings:
    """Minimal runtime settings shared across scripts and services."""

    app_name: str = "invest_bot"
    market: str = "domestic_stock"
    trading_mode: TradingMode = TradingMode.MOCK
    environment: str = "local"
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "AppSettings":
        mode = os.getenv("INVEST_BOT_TRADING_MODE", TradingMode.MOCK.value).lower()
        return cls(
            app_name=os.getenv("INVEST_BOT_APP_NAME", "invest_bot"),
            market=os.getenv("INVEST_BOT_MARKET", "domestic_stock"),
            trading_mode=TradingMode(mode),
            environment=os.getenv("INVEST_BOT_ENV", "local"),
            log_level=os.getenv("INVEST_BOT_LOG_LEVEL", "INFO").upper(),
        )
