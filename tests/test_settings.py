from pathlib import Path

from invest_bot.config.settings import AppSettings, TradingMode


def test_app_settings_defaults_to_mock_mode(tmp_path: Path):
    settings = AppSettings.from_file(tmp_path / "missing.yaml")

    assert settings.market == "domestic_stock"
    assert settings.trading_mode is TradingMode.MOCK


def test_app_settings_loads_file_values(tmp_path: Path):
    config_path = tmp_path / "app.yaml"
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
            ]
        ),
        encoding="utf-8",
    )

    settings = AppSettings.from_file(config_path)

    assert settings.app_name == "custom_bot"
    assert settings.kis_app_key == "live-key"
    assert settings.kis_app_secret == "live-secret"
    assert settings.trading_mode is TradingMode.LIVE
