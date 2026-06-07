from invest_bot.config.settings import AppSettings, TradingMode
from tests.helpers import make_test_dir


def test_app_settings_defaults_to_mock_mode():
    test_dir = make_test_dir("settings_defaults")
    settings = AppSettings.from_file(test_dir / "missing.yaml")

    assert settings.market == "domestic_stock"
    assert settings.trading_mode is TradingMode.MOCK
    assert settings.database_url == "postgresql+psycopg://invest_bot:invest_bot@localhost:5432/invest_bot"
    assert settings.enable_db_write is False


def test_app_settings_loads_file_values():
    test_dir = make_test_dir("settings_load")
    config_path = test_dir / "app.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app_name: custom_bot",
                "market: domestic_stock",
                "trading_mode: live",
                "environment: test",
                "log_level: debug",
                "kis_app_key: live-key",
                "kis_app_secret: live-secret",
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

    settings = AppSettings.from_file(config_path)

    assert settings.app_name == "custom_bot"
    assert settings.kis_app_key == "live-key"
    assert settings.kis_app_secret == "live-secret"
    assert settings.trading_mode is TradingMode.LIVE
    assert settings.enable_db_write is True


def test_app_settings_reads_database_env_contract(monkeypatch):
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
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///tmp/invest_bot.db")

    settings = AppSettings()

    assert settings.database_url == "sqlite+pysqlite:///tmp/invest_bot.db"
