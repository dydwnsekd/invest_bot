from __future__ import annotations

import argparse
from invest_bot.jobs.generate_golden_cross_signals import (
    GoldenCrossSignalGenerator,
    GoldenCrossSignalRequest,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate golden cross signals from indicator CSV files.")
    parser.add_argument("symbol", nargs="?", default="005930", help="Stock symbol to analyze.")
    return parser.parse_args()


def generate_golden_cross_signals_for_symbol(
    symbol: str,
    generator: GoldenCrossSignalGenerator | None = None,
) -> dict[str, str | int]:
    signal_generator = generator or GoldenCrossSignalGenerator()
    source_filename = signal_generator.processed_storage.latest_filename("daily_prices_indicators", symbol)
    if source_filename is None:
        raise FileNotFoundError(f"No daily_prices_indicators dataset found for symbol '{symbol}'. Run daily analysis first.")
    request = GoldenCrossSignalRequest(symbol=symbol, source_filename=source_filename)
    indicator_frame = signal_generator.load_indicator_frame(request)
    signal_frame = signal_generator.generate_signals(indicator_frame)
    saved = signal_generator.save_signals(request.source_filename, signal_frame)
    return {
        "symbol": symbol,
        "source_file": source_filename,
        "indicator_rows": len(indicator_frame),
        "signal_rows": len(signal_frame),
        "saved_path": str(saved.path),
    }


def main() -> None:
    args = _parse_args()
    symbol = args.symbol
    try:
        result = generate_golden_cross_signals_for_symbol(symbol)
    except FileNotFoundError as error:
        raise SystemExit(
            "\n".join(
                [
                    str(error),
                    "",
                    "Prepare the inputs in this order:",
                    "1. python scripts/run_collection.py <symbol>",
                    "2. python scripts/run_daily_analysis.py <symbol>",
                    "3. python scripts/run_golden_cross_signals.py <symbol>",
                ]
            )
        ) from error

    print(result)


if __name__ == "__main__":
    main()
