from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import quote_plus

import yaml


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
    database_url_value: str = ""
    db_host: str = "localhost"
    db_host_docker: str = ""
    db_port: int = 5432
    db_name: str = "invest_bot"
    db_user: str = "invest_bot"
    db_password: str = "invest_bot"
    enable_db_write: bool = False
    stock_master_update_on_startup: bool = True
    stock_master_refresh_interval_minutes: int = 1440

    @classmethod
    def from_file(
        cls,
        path: str | Path | None = None,
    ) -> "AppSettings":
        settings_path = Path(path) if path is not None else CONFIG_DIR / "app.yaml"
        raw_data: dict[str, object] = {}
        if settings_path.exists():
            loaded = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
            raw_data = {str(key): value for key, value in loaded.items()}

        def configured_value(yaml_key: str, default: str) -> str:
            configured = raw_data.get(yaml_key, default)
            return str(configured)

        def configured_bool(yaml_key: str, default: bool = False) -> bool:
            configured = raw_data.get(yaml_key, default)
            if isinstance(configured, bool):
                return configured
            return str(configured).strip().lower() in {"1", "true", "yes", "on"}

        mode = configured_value("trading_mode", TradingMode.MOCK.value).lower()
        return cls(
            app_name=configured_value("app_name", "invest_bot"),
            market=configured_value("market", "domestic_stock"),
            trading_mode=TradingMode(mode),
            environment=configured_value("environment", "local"),
            log_level=configured_value("log_level", "INFO").upper(),
            kis_live_app_key=configured_value("kis_live_app_key", ""),
            kis_live_app_secret=configured_value("kis_live_app_secret", ""),
            kis_mock_app_key=configured_value("kis_mock_app_key", ""),
            kis_mock_app_secret=configured_value("kis_mock_app_secret", ""),
            database_url_value=configured_value("database_url", "").strip(),
            db_host=configured_value("db_host", "localhost"),
            db_host_docker=configured_value("db_host_docker", "").strip(),
            db_port=int(configured_value("db_port", "5432")),
            db_name=configured_value("db_name", "invest_bot"),
            db_user=configured_value("db_user", "invest_bot"),
            db_password=configured_value("db_password", "invest_bot"),
            enable_db_write=configured_bool("enable_db_write", False),
            stock_master_update_on_startup=configured_bool("stock_master_update_on_startup", True),
            stock_master_refresh_interval_minutes=max(int(configured_value("stock_master_refresh_interval_minutes", "1440")), 1),
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
        if self.database_url_value:
            return self.database_url_value

        host = self._resolve_database_host()

        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        name = quote_plus(self.db_name)
        return f"postgresql+psycopg://{user}:{password}@{host}:{self.db_port}/{name}"

    def _resolve_database_host(self) -> str:
        if self._use_docker_network_host():
            return self.db_host_docker or "db"
        return self.db_host

    def _use_docker_network_host(self) -> bool:
        return os.getenv("INVEST_BOT_APP_ROLE", "").strip() in {
            "migrate",
            "scheduler",
            "web",
            "collector",
        }
