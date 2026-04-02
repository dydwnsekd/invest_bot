from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml


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
    kis_live_app_key: str = ""
    kis_live_app_secret: str = ""
    kis_mock_app_key: str = ""
    kis_mock_app_secret: str = ""

    @classmethod
    def from_file(
        cls,
        path: str | Path | None = None,
        credentials_path: str | Path | None = None,
    ) -> "AppSettings":
        settings_path = Path(path) if path is not None else Path("config") / "app.yaml"
        raw_data: dict[str, str] = {}
        if settings_path.exists():
            loaded = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
            raw_data = {str(key): value for key, value in loaded.items()}

        if credentials_path is None and path is None:
            credentials_file = Path("config") / "kis_credentials.yaml"
        elif credentials_path is not None:
            credentials_file = Path(credentials_path)
        else:
            credentials_file = None

        if credentials_file is not None and credentials_file.exists():
            loaded_credentials = yaml.safe_load(credentials_file.read_text(encoding="utf-8")) or {}
            raw_data.update({str(key): value for key, value in loaded_credentials.items()})

        mode = str(raw_data.get("trading_mode", TradingMode.MOCK.value)).lower()
        return cls(
            app_name=str(raw_data.get("app_name", "invest_bot")),
            market=str(raw_data.get("market", "domestic_stock")),
            trading_mode=TradingMode(mode),
            environment=str(raw_data.get("environment", "local")),
            log_level=str(raw_data.get("log_level", "INFO")).upper(),
            kis_live_app_key=str(raw_data.get("kis_app_key", "")),
            kis_live_app_secret=str(raw_data.get("kis_app_secret", "")),
            kis_mock_app_key=str(raw_data.get("kis_mock_app_key", "")),
            kis_mock_app_secret=str(raw_data.get("kis_mock_app_secret", "")),
        )

    @property
    def kis_base_url(self) -> str:
        if self.trading_mode is TradingMode.LIVE:
            return "https://openapi.koreainvestment.com:9443"
        return "https://openapivts.koreainvestment.com:29443"

    @property
    def kis_app_key(self) -> str:
        if self.trading_mode is TradingMode.LIVE:
            return self.kis_live_app_key
        return self.kis_mock_app_key

    @property
    def kis_app_secret(self) -> str:
        if self.trading_mode is TradingMode.LIVE:
            return self.kis_live_app_secret
        return self.kis_mock_app_secret
