from invest_bot.config.settings import AppSettings, TradingMode
from tests.helpers import make_test_dir


def _clear_settings_env(monkeypatch) -> None:
    for key in [
        "DATABASE_URL",
        "INVEST_BOT_APP_NAME",
        "INVEST_BOT_MARKET",
        "INVEST_BOT_TRADING_MODE",
        "INVEST_BOT_ENVIRONMENT",
        "INVEST_BOT_LOG_LEVEL",
        "INVEST_BOT_DB_HOST",
        "INVEST_BOT_DB_PORT",
        "INVEST_BOT_DB_NAME",
        "INVEST_BOT_DB_USER",
        "INVEST_BOT_DB_PASSWORD",
        "INVEST_BOT_ENABLE_DB_WRITE",
        "INVEST_BOT_KIS_APP_KEY",
        "INVEST_BOT_KIS_APP_SECRET",
        "INVEST_BOT_KIS_MOCK_APP_KEY",
        "INVEST_BOT_KIS_MOCK_APP_SECRET",
    ]:
        monkeypatch.delenv(key, raising=False)


def _disable_project_dotenv(monkeypatch) -> None:
    monkeypatch.setattr("invest_bot.config.settings.load_dotenv", lambda *args, **kwargs: None)


def test_app_settings_defaults_to_mock_mode(monkeypatch):
    _clear_settings_env(monkeypatch)
    _disable_project_dotenv(monkeypatch)
    test_dir = make_test_dir("settings_defaults")
    settings = AppSettings.from_file(test_dir / "missing.yaml")

    assert settings.market == "domestic_stock"
    assert settings.trading_mode is TradingMode.MOCK
    assert settings.database_url == "postgresql+psycopg://invest_bot:invest_bot@localhost:5432/invest_bot"
    assert settings.enable_db_write is False


def test_app_settings_loads_file_values(monkeypatch):
    _clear_settings_env(monkeypatch)
    _disable_project_dotenv(monkeypatch)
    test_dir = make_test_dir("settings_load")
    config_path = test_dir / "app.yaml"
    credentials_path = test_dir / "kis_credentials.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app_name: custom_bot",
                "market: domestic_stock",
                "trading_mode: live",
                "environment: test",
                "log_level: debug",
                "db_host: db",
                "db_port: 5433",
                "db_name: custom_db",
                "db_user: db_user",
                "db_password: db_password",
                "enable_db_write: true",
            ]
        ),
        encoding="utf-8",
    )
    credentials_path.write_text(
        "\n".join(
            [
                "kis_app_key: live-key",
                "kis_app_secret: live-secret",
                "kis_mock_app_key: mock-key",
                "kis_mock_app_secret: mock-secret",
            ]
        ),
        encoding="utf-8",
    )

    settings = AppSettings.from_file(config_path, credentials_path)

    assert settings.app_name == "custom_bot"
    assert settings.kis_app_key == "live-key"
    assert settings.kis_app_secret == "live-secret"
    assert settings.trading_mode is TradingMode.LIVE
    assert settings.enable_db_write is True


def test_app_settings_reads_database_env_contract(monkeypatch):
    _clear_settings_env(monkeypatch)
    _disable_project_dotenv(monkeypatch)
    monkeypatch.setenv("INVEST_BOT_DB_HOST", "db")
    monkeypatch.setenv("INVEST_BOT_DB_PORT", "15432")
    monkeypatch.setenv("INVEST_BOT_DB_NAME", "invest_bot_dev")
    monkeypatch.setenv("INVEST_BOT_DB_USER", "tester")
    monkeypatch.setenv("INVEST_BOT_DB_PASSWORD", "secret")
    monkeypatch.setenv("INVEST_BOT_ENABLE_DB_WRITE", "true")

    test_dir = make_test_dir("settings_db_env")
    settings = AppSettings.from_file(test_dir / "missing.yaml")

    assert settings.db_host == "db"
    assert settings.db_port == 15432
    assert settings.db_name == "invest_bot_dev"
    assert settings.db_user == "tester"
    assert settings.db_password == "secret"
    assert settings.enable_db_write is True
    assert settings.database_url == "postgresql+psycopg://tester:secret@db:15432/invest_bot_dev"


def test_app_settings_prefers_explicit_database_url(monkeypatch):
    _clear_settings_env(monkeypatch)
    _disable_project_dotenv(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///tmp/invest_bot.db")

    settings = AppSettings()

    assert settings.database_url == "sqlite+pysqlite:///tmp/invest_bot.db"


def test_app_settings_ignores_kis_env_vars_and_reads_credentials_file(monkeypatch):
    _clear_settings_env(monkeypatch)
    _disable_project_dotenv(monkeypatch)
    monkeypatch.setenv("INVEST_BOT_KIS_APP_KEY", "env-live-key")
    monkeypatch.setenv("INVEST_BOT_KIS_APP_SECRET", "env-live-secret")
    monkeypatch.setenv("INVEST_BOT_KIS_MOCK_APP_KEY", "env-mock-key")
    monkeypatch.setenv("INVEST_BOT_KIS_MOCK_APP_SECRET", "env-mock-secret")

    test_dir = make_test_dir("settings_credentials_only")
    credentials_path = test_dir / "kis_credentials.yaml"
    credentials_path.write_text(
        "\n".join(
            [
                "kis_app_key: file-live-key",
                "kis_app_secret: file-live-secret",
                "kis_mock_app_key: file-mock-key",
                "kis_mock_app_secret: file-mock-secret",
            ]
        ),
        encoding="utf-8",
    )

    settings = AppSettings.from_file(test_dir / "missing.yaml", credentials_path)

    assert settings.kis_live_app_key == "file-live-key"
    assert settings.kis_live_app_secret == "file-live-secret"
    assert settings.kis_mock_app_key == "file-mock-key"
    assert settings.kis_mock_app_secret == "file-mock-secret"
