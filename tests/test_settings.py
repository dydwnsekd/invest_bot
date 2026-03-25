from invest_bot.config.settings import AppSettings, TradingMode


def test_app_settings_defaults_to_mock_mode(monkeypatch):
    monkeypatch.delenv("INVEST_BOT_TRADING_MODE", raising=False)

    settings = AppSettings.from_env()

    assert settings.market == "domestic_stock"
    assert settings.trading_mode is TradingMode.MOCK
