from __future__ import annotations

import argparse
from pathlib import Path

from invest_bot.jobs.generate_market_report import MarketReportGenerator, MarketReportRequest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a current market summary report.")
    parser.add_argument("symbol", nargs="?", default="005930", help="Stock symbol to analyze.")
    return parser.parse_args()


def _find_latest_file(directory: Path, pattern: str) -> Path:
    if not directory.exists():
        raise FileNotFoundError(
            f"Required directory does not exist: '{directory}'. "
            "Run data collection, indicator analysis, and signal generation first."
        )
    matches = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    if not matches:
        available = ", ".join(path.name for path in sorted(directory.glob("*.csv"))[:10]) or "no csv files found"
        raise FileNotFoundError(
            f"No files matched pattern '{pattern}' in '{directory}'. "
            f"Available files: {available}. "
            "Run collection -> daily analysis -> golden cross signals before generating the market report."
        )
    return matches[0]


def main() -> None:
    args = _parse_args()
    generator = MarketReportGenerator()
    symbol = args.symbol

    try:
        indicator_file = _find_latest_file(
            generator.processed_storage.root_dir / "daily_prices_indicators",
            f"{symbol}_*.csv",
        )
        signal_file = _find_latest_file(
            generator.processed_storage.root_dir / "golden_cross_signals",
            f"{symbol}_*.csv",
        )
        investor_file = _find_latest_file(
            generator.raw_storage.root_dir / "investor_daily",
            f"{symbol}_*.csv",
        )
    except FileNotFoundError as error:
        raise SystemExit(
            "\n".join(
                [
                    str(error),
                    "",
                    "Prepare the inputs in this order:",
                    "1. python scripts/run_collection.py <symbol>",
                    "2. python scripts/run_daily_analysis.py",
                    "3. python scripts/run_golden_cross_signals.py",
                    "4. python scripts/run_market_report.py <symbol>",
                ]
            )
        ) from error

    request = MarketReportRequest(
        symbol=symbol,
        indicator_filename=indicator_file.name,
        signal_filename=signal_file.name,
        investor_filename=investor_file.name,
    )
    indicator_frame = generator.load_indicator_frame(request)
    signal_frame = generator.load_signal_frame(request)
    investor_frame = generator.load_investor_frame(request)
    stock_info_frame = generator.load_stock_info_frame(request)

    report = generator.generate_report(
        request=request,
        indicator_frame=indicator_frame,
        signal_frame=signal_frame,
        investor_frame=investor_frame,
        stock_info_frame=stock_info_frame,
    )
    report_date = report.iloc[0]["date"] if not report.empty else "latest"
    report_suffix = str(report_date).replace("-", "")
    saved = generator.save_report(f"{symbol}_{report_suffix}.csv", report)
    print(
        {
            "symbol": symbol,
            "rows": len(report),
            "indicator_file": indicator_file.name,
            "signal_file": signal_file.name,
            "investor_file": investor_file.name,
            "saved_path": str(saved.path),
        }
    )


if __name__ == "__main__":
    main()
