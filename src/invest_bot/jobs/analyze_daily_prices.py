from __future__ import annotations

import argparse
from pathlib import Path

from invest_bot.market.analysis import DailyPriceAnalyzer, IndicatorRequest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate indicator CSV files from collected daily prices.")
    parser.add_argument("symbol", nargs="?", default="005930", help="Stock symbol to analyze.")
    return parser.parse_args()


def _find_latest_file(directory: Path, pattern: str) -> Path:
    if not directory.exists():
        raise FileNotFoundError(
            f"Required directory does not exist: '{directory}'. Run collection first."
        )
    matches = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    if not matches:
        available = ", ".join(path.name for path in sorted(directory.glob("*.csv"))[:10]) or "no csv files found"
        raise FileNotFoundError(
            f"No files matched pattern '{pattern}' in '{directory}'. "
            f"Available files: {available}. Run collection first."
        )
    return matches[0]


def generate_indicators_for_symbol(symbol: str, analyzer: DailyPriceAnalyzer | None = None) -> dict[str, str | int]:
    price_analyzer = analyzer or DailyPriceAnalyzer()
    source_file = _find_latest_file(
        price_analyzer.raw_storage.root_dir / "daily_prices",
        f"{symbol}_*.csv",
    )
    request = IndicatorRequest(symbol=symbol, source_filename=source_file.name)
    daily_prices = price_analyzer.load_daily_prices(request)
    indicators = price_analyzer.calculate_indicators(daily_prices)
    saved = price_analyzer.save_indicators(request.source_filename, indicators)
    return {
        "symbol": symbol,
        "source_file": source_file.name,
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
