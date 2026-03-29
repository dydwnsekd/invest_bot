from __future__ import annotations

from datetime import date, timedelta

from invest_bot.config.settings import AppSettings
from invest_bot.market.collector import MarketDataCollector


def main() -> None:
    settings = AppSettings.from_file()
    collector = MarketDataCollector(settings)
    today = date.today()
    summary, prices = collector.collect_daily_prices("005930", today - timedelta(days=30), today)
    stock_info = collector.collect_stock_info("005930")
    investor_daily, investor_summary = collector.collect_investor_daily("005930", today)
    print(
        {
            "app_name": settings.app_name,
            "market": settings.market,
            "trading_mode": settings.trading_mode.value,
            "daily_summary_rows": len(summary),
            "daily_price_rows": len(prices),
            "stock_info_rows": len(stock_info),
            "investor_daily_rows": len(investor_daily),
            "investor_summary_rows": len(investor_summary),
        }
    )


if __name__ == "__main__":
    main()
