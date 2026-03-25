from __future__ import annotations

from invest_bot.config.settings import AppSettings
from invest_bot.market.collector import CollectionRequest, MarketDataCollector


def main() -> None:
    settings = AppSettings.from_env()
    collector = MarketDataCollector()
    result = collector.collect(CollectionRequest(symbol="005930"))
    print(
        {
            "app_name": settings.app_name,
            "market": settings.market,
            "trading_mode": settings.trading_mode.value,
            "result": result,
        }
    )


if __name__ == "__main__":
    main()
