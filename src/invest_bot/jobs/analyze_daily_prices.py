from __future__ import annotations

import argparse
from invest_bot.market.analysis import DailyPriceAnalyzer, IndicatorRequest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate indicator CSV files from collected daily prices.")
    parser.add_argument("symbol", nargs="?", default="005930", help="Stock symbol to analyze.")
    return parser.parse_args()


def generate_indicators_for_symbol(symbol: str, analyzer: DailyPriceAnalyzer | None = None) -> dict[str, str | int]:
    price_analyzer = analyzer or DailyPriceAnalyzer()
    source_filename = price_analyzer.raw_storage.latest_filename("daily_prices", symbol)
    if source_filename is None:
        raise FileNotFoundError(f"No daily_prices dataset found for symbol '{symbol}'. Run collection first.")
    request = IndicatorRequest(symbol=symbol, source_filename=source_filename)
    daily_prices = price_analyzer.load_daily_prices(request)
    indicators = price_analyzer.calculate_indicators(daily_prices)
    saved = price_analyzer.save_indicators(request.source_filename, indicators)
    return {
        "symbol": symbol,
        "source_file": source_filename,
        "source_rows": len(daily_prices),
        "indicator_rows": len(indicators),
        "saved_path": str(saved.path),
    }


def main() -> None:
    args = _parse_args()
    symbol = args.symbol
    try:
        result = generate_indicators_for_symbol(symbol)
    except FileNotFoundError as error:
        raise SystemExit(
            "\n".join(
                [
                    str(error),
                    "",
                    "Prepare the inputs in this order:",
                    "1. python scripts/run_collection.py <symbol>",
                    "2. python scripts/run_daily_analysis.py <symbol>",
                ]
            )
        ) from error

    print(result)


if __name__ == "__main__":
    main()
