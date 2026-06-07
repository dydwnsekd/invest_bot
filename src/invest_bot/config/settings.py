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
    enable_db_write: bool = False

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

        def configured_value(env_name: str, yaml_key: str, default: str) -> str:
            value = os.getenv(env_name)
            if value is not None:
                return value
            configured = raw_data.get(yaml_key, default)
            return str(configured)

        def configured_bool(env_name: str, yaml_key: str, default: bool = False) -> bool:
            value = os.getenv(env_name)
            if value is not None:
                return value.strip().lower() in {"1", "true", "yes", "on"}
            configured = raw_data.get(yaml_key, default)
            if isinstance(configured, bool):
                return configured
            return str(configured).strip().lower() in {"1", "true", "yes", "on"}

        mode = configured_value("INVEST_BOT_TRADING_MODE", "trading_mode", TradingMode.MOCK.value).lower()
        return cls(
            app_name=configured_value("INVEST_BOT_APP_NAME", "app_name", "invest_bot"),
            market=configured_value("INVEST_BOT_MARKET", "market", "domestic_stock"),
            trading_mode=TradingMode(mode),
            environment=configured_value("INVEST_BOT_ENVIRONMENT", "environment", "local"),
            log_level=configured_value("INVEST_BOT_LOG_LEVEL", "log_level", "INFO").upper(),
            kis_live_app_key=configured_value("INVEST_BOT_KIS_APP_KEY", "kis_app_key", ""),
            kis_live_app_secret=configured_value("INVEST_BOT_KIS_APP_SECRET", "kis_app_secret", ""),
            kis_mock_app_key=configured_value("INVEST_BOT_KIS_MOCK_APP_KEY", "kis_mock_app_key", ""),
            kis_mock_app_secret=configured_value("INVEST_BOT_KIS_MOCK_APP_SECRET", "kis_mock_app_secret", ""),
            db_host=configured_value("INVEST_BOT_DB_HOST", "db_host", "localhost"),
            db_port=int(configured_value("INVEST_BOT_DB_PORT", "db_port", "5432")),
            db_name=configured_value("INVEST_BOT_DB_NAME", "db_name", "invest_bot"),
            db_user=configured_value("INVEST_BOT_DB_USER", "db_user", "invest_bot"),
            db_password=configured_value("INVEST_BOT_DB_PASSWORD", "db_password", "invest_bot"),
            enable_db_write=configured_bool("INVEST_BOT_ENABLE_DB_WRITE", "enable_db_write", False),
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
        direct_url = os.getenv("DATABASE_URL", "").strip()
        if direct_url:
            return direct_url

        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        name = quote_plus(self.db_name)
        return f"postgresql+psycopg://{user}:{password}@{self.db_host}:{self.db_port}/{name}"
