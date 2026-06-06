from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import quote_plus

import yaml
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = PROJECT_ROOT / "config"


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
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "invest_bot"
    db_user: str = "invest_bot"
    db_password: str = "invest_bot"

    @classmethod
    def from_file(
        cls,
        path: str | Path | None = None,
        credentials_path: str | Path | None = None,
    ) -> "AppSettings":
        load_dotenv(PROJECT_ROOT / ".env", override=False)

        settings_path = Path(path) if path is not None else CONFIG_DIR / "app.yaml"
        raw_data: dict[str, object] = {}
        if settings_path.exists():
            loaded = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
            raw_data = {str(key): value for key, value in loaded.items()}

        if credentials_path is None and path is None:
            credentials_file = CONFIG_DIR / "kis_credentials.yaml"
        elif credentials_path is not None:
            credentials_file = Path(credentials_path)
        else:
            credentials_file = None

        if credentials_file is not None and credentials_file.exists():
            loaded_credentials = yaml.safe_load(credentials_file.read_text(encoding="utf-8")) or {}
            raw_data.update({str(key): value for key, value in loaded_credentials.items()})

        raw_data.update(_load_environment_overrides())

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
            db_host=str(raw_data.get("db_host", "localhost")),
            db_port=int(raw_data.get("db_port", 5432)),
            db_name=str(raw_data.get("db_name", "invest_bot")),
            db_user=str(raw_data.get("db_user", "invest_bot")),
            db_password=str(raw_data.get("db_password", "invest_bot")),
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

    @property
    def database_url(self) -> str:
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        host = self.db_host.strip() or "localhost"
        return f"postgresql://{user}:{password}@{host}:{self.db_port}/{self.db_name}"


def _load_environment_overrides() -> dict[str, object]:
    mapping = {
        "app_name": "INVEST_BOT_APP_NAME",
        "market": "INVEST_BOT_MARKET",
        "trading_mode": "INVEST_BOT_TRADING_MODE",
        "environment": "INVEST_BOT_ENVIRONMENT",
        "log_level": "INVEST_BOT_LOG_LEVEL",
        "kis_app_key": "INVEST_BOT_KIS_APP_KEY",
        "kis_app_secret": "INVEST_BOT_KIS_APP_SECRET",
        "kis_mock_app_key": "INVEST_BOT_KIS_MOCK_APP_KEY",
        "kis_mock_app_secret": "INVEST_BOT_KIS_MOCK_APP_SECRET",
        "db_host": "INVEST_BOT_DB_HOST",
        "db_port": "INVEST_BOT_DB_PORT",
        "db_name": "INVEST_BOT_DB_NAME",
        "db_user": "INVEST_BOT_DB_USER",
        "db_password": "INVEST_BOT_DB_PASSWORD",
    }
    overrides: dict[str, object] = {}
    for key, env_name in mapping.items():
        value = os.getenv(env_name)
        if value not in (None, ""):
            overrides[key] = value
    return overrides
