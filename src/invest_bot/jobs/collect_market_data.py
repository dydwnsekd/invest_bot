from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date, timedelta

from invest_bot.config.settings import AppSettings
from invest_bot.market.collector import MarketDataCollector


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect domestic stock market datasets.")
    parser.add_argument("symbols", nargs="*", help="One or more stock symbols to collect.")
    parser.add_argument(
        "--symbols-file",
        dest="symbols_file",
        help="Optional text file containing one stock symbol per line.",
    )
    parser.add_argument("--days", type=int, default=30, help="Number of days of daily price history to collect.")
    return parser.parse_args()


def _load_symbols(args: argparse.Namespace) -> list[str]:
    symbols = list(args.symbols)
    if args.symbols_file:
        with open(args.symbols_file, encoding="utf-8") as file:
            for line in file:
                symbol = line.strip()
                if symbol:
                    symbols.append(symbol)
    unique_symbols: list[str] = []
    seen: set[str] = set()
    for symbol in symbols or ["005930"]:
        if symbol not in seen:
            unique_symbols.append(symbol)
            seen.add(symbol)
    return unique_symbols


def collect_market_data_for_symbols(
    symbols: list[str],
    days: int = 30,
    settings: AppSettings | None = None,
    collector: MarketDataCollector | None = None,
) -> dict[str, object]:
    resolved_settings = settings or AppSettings.from_file()
    market_collector = collector or MarketDataCollector(resolved_settings)
    today = date.today()
    start_date = today - timedelta(days=days)

    unique_symbols: list[str] = []
    seen: set[str] = set()
    for symbol in symbols or ["005930"]:
        normalized = symbol.strip()
        if normalized and normalized not in seen:
            unique_symbols.append(normalized)
            seen.add(normalized)

    results = market_collector.collect_symbols_batch(symbols=unique_symbols, start_date=start_date, end_date=today)
    return {
        "app_name": resolved_settings.app_name,
        "market": resolved_settings.market,
        "trading_mode": resolved_settings.trading_mode.value,
        "symbol_count": len(unique_symbols),
        "symbols": unique_symbols,
        "days": days,
        "success_count": sum(1 for result in results if result.status == "success"),
        "failed_count": sum(1 for result in results if result.status == "failed"),
        "results": [asdict(result) for result in results],
    }


def main() -> None:
    args = _parse_args()
    symbols = _load_symbols(args)
    print(collect_market_data_for_symbols(symbols=symbols, days=args.days))


if __name__ == "__main__":
    main()
