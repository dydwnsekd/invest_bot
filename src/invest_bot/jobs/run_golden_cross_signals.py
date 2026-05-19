from __future__ import annotations

import argparse
from pathlib import Path

from invest_bot.jobs.generate_golden_cross_signals import (
    GoldenCrossSignalGenerator,
    GoldenCrossSignalRequest,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate golden cross signals from indicator CSV files.")
    parser.add_argument("symbol", nargs="?", default="005930", help="Stock symbol to analyze.")
    return parser.parse_args()


def _find_latest_file(directory: Path, pattern: str) -> Path:
    if not directory.exists():
        raise FileNotFoundError(
            f"Required directory does not exist: '{directory}'. Run daily analysis first."
        )
    matches = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    if not matches:
        available = ", ".join(path.name for path in sorted(directory.glob("*.csv"))[:10]) or "no csv files found"
        raise FileNotFoundError(
            f"No files matched pattern '{pattern}' in '{directory}'. "
            f"Available files: {available}. Run daily analysis first."
        )
    return matches[0]


def generate_golden_cross_signals_for_symbol(
    symbol: str,
    generator: GoldenCrossSignalGenerator | None = None,
) -> dict[str, str | int]:
    signal_generator = generator or GoldenCrossSignalGenerator()
    source_file = _find_latest_file(
        signal_generator.processed_storage.root_dir / "daily_prices_indicators",
        f"{symbol}_*.csv",
    )
    request = GoldenCrossSignalRequest(symbol=symbol, source_filename=source_file.name)
    indicator_frame = signal_generator.load_indicator_frame(request)
    signal_frame = signal_generator.generate_signals(indicator_frame)
    saved = signal_generator.save_signals(request.source_filename, signal_frame)
    return {
        "symbol": symbol,
        "source_file": source_file.name,
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
