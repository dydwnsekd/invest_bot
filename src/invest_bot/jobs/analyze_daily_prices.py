from __future__ import annotations

from invest_bot.market.analysis import DailyPriceAnalyzer, IndicatorRequest


def main() -> None:
    analyzer = DailyPriceAnalyzer()
    request = IndicatorRequest(symbol="005930", source_filename="005930_20260301_20260329.csv")
    daily_prices = analyzer.load_daily_prices(request)
    indicators = analyzer.calculate_indicators(daily_prices)
    saved = analyzer.save_indicators(request.source_filename, indicators)
    print(
        {
            "source_rows": len(daily_prices),
            "indicator_rows": len(indicators),
            "saved_path": str(saved.path),
        }
    )


if __name__ == "__main__":
    main()
