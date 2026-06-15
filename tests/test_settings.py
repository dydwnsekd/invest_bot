from invest_bot.config.settings import AppSettings, TradingMode
from tests.helpers import make_test_dir


def _clear_settings_env(monkeypatch) -> None:
    for key in ["DATABASE_URL", "INVEST_BOT_DB_HOST", "INVEST_BOT_DB_PORT", "INVEST_BOT_DB_NAME", "INVEST_BOT_DB_USER", "INVEST_BOT_DB_PASSWORD"]:
        monkeypatch.delenv(key, raising=False)


def test_app_settings_defaults_to_mock_mode(monkeypatch):
    _clear_settings_env(monkeypatch)
    test_dir = make_test_dir("settings_defaults")
    settings = AppSettings.from_file(test_dir / "missing.yaml")

    assert settings.market == "domestic_stock"
    assert settings.trading_mode is TradingMode.MOCK
    assert settings.database_url == "postgresql+psycopg://invest_bot:invest_bot@localhost:5432/invest_bot"
    assert settings.enable_db_write is False


def test_app_settings_loads_file_values(monkeypatch):
    _clear_settings_env(monkeypatch)
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
                "kis_live_app_key: live-key",
                "kis_live_app_secret: live-secret",
                "kis_mock_app_key: mock-key",
                "kis_mock_app_secret: mock-secret",
                "db_host: db",
                "db_host_docker: db-internal",
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


def test_app_settings_builds_database_url_from_file_values(monkeypatch):
    _clear_settings_env(monkeypatch)
    test_dir = make_test_dir("settings_db_file")
    config_path = test_dir / "app.yaml"
    config_path.write_text(
        "\n".join(
            [
                "db_host: db",
                "db_host_docker: db-internal",
                "db_port: 15432",
                "db_name: invest_bot_dev",
                "db_user: tester",
                "db_password: secret",
                "enable_db_write: true",
            ]
        ),
        encoding="utf-8",
    )

    settings = AppSettings.from_file(config_path)

    assert settings.db_host == "db"
    assert settings.db_port == 15432
    assert settings.db_name == "invest_bot_dev"
    assert settings.db_user == "tester"
    assert settings.db_password == "secret"
    assert settings.enable_db_write is True
    assert settings.database_url == "postgresql+psycopg://tester:secret@db:15432/invest_bot_dev"


def test_app_settings_uses_docker_host_override_inside_compose_runtime(monkeypatch):
    _clear_settings_env(monkeypatch)
    monkeypatch.setenv("INVEST_BOT_APP_ROLE", "web")
    test_dir = make_test_dir("settings_db_docker_override")
    config_path = test_dir / "app.yaml"
    config_path.write_text(
        "\n".join(
            [
                "db_host: localhost",
                "db_host_docker: db",
                "db_port: 5432",
                "db_name: invest_bot",
                "db_user: invest_bot",
                "db_password: invest_bot",
            ]
        ),
        encoding="utf-8",
    )

    settings = AppSettings.from_file(config_path)

    assert settings.database_url == "postgresql+psycopg://invest_bot:invest_bot@db:5432/invest_bot"


def test_app_settings_defaults_to_compose_db_host_when_override_missing(monkeypatch):
    _clear_settings_env(monkeypatch)
    monkeypatch.setenv("INVEST_BOT_APP_ROLE", "web")
    test_dir = make_test_dir("settings_db_docker_default")
    config_path = test_dir / "app.yaml"
    config_path.write_text(
        "\n".join(
            [
                "db_host: localhost",
                "db_port: 5432",
                "db_name: invest_bot",
                "db_user: invest_bot",
                "db_password: invest_bot",
            ]
        ),
        encoding="utf-8",
    )

    settings = AppSettings.from_file(config_path)

    assert settings.database_url == "postgresql+psycopg://invest_bot:invest_bot@db:5432/invest_bot"


def test_app_settings_prefers_database_url_from_file(monkeypatch):
    _clear_settings_env(monkeypatch)
    test_dir = make_test_dir("settings_direct_url")
    config_path = test_dir / "app.yaml"
    config_path.write_text("database_url: sqlite+pysqlite:///tmp/invest_bot.db\n", encoding="utf-8")

    settings = AppSettings.from_file(config_path)

    assert settings.database_url == "sqlite+pysqlite:///tmp/invest_bot.db"


def test_app_settings_reads_kis_credentials_from_app_yaml(monkeypatch):
    _clear_settings_env(monkeypatch)
    test_dir = make_test_dir("settings_credentials_in_app")
    config_path = test_dir / "app.yaml"
    config_path.write_text(
        "\n".join(
            [
                "kis_live_app_key: file-live-key",
                "kis_live_app_secret: file-live-secret",
                "kis_mock_app_key: file-mock-key",
                "kis_mock_app_secret: file-mock-secret",
            ]
        ),
        encoding="utf-8",
    )

    settings = AppSettings.from_file(config_path)

    assert settings.kis_live_app_key == "file-live-key"
    assert settings.kis_live_app_secret == "file-live-secret"
    assert settings.kis_mock_app_key == "file-mock-key"
    assert settings.kis_mock_app_secret == "file-mock-secret"
