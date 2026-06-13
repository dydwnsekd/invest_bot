from __future__ import annotations

import argparse
from invest_bot.jobs.generate_market_report import MarketReportGenerator, MarketReportRequest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a current market summary report.")
    parser.add_argument("symbol", nargs="?", default="005930", help="Stock symbol to analyze.")
    return parser.parse_args()


def generate_market_report_for_symbol(symbol: str, generator: MarketReportGenerator | None = None) -> dict[str, str | int]:
    report_generator = generator or MarketReportGenerator()
    indicator_filename = report_generator.processed_storage.latest_filename("daily_prices_indicators", symbol)
    signal_filename = report_generator.processed_storage.latest_filename("golden_cross_signals", symbol)
    investor_filename = report_generator.raw_storage.latest_filename("investor_daily", symbol)
    if not indicator_filename or not signal_filename or not investor_filename:
        raise FileNotFoundError(
            "Missing one or more required datasets for market report generation. "
            "Run collection -> daily analysis -> golden cross signals first."
        )

    request = MarketReportRequest(
        symbol=symbol,
        indicator_filename=indicator_filename,
        signal_filename=signal_filename,
        investor_filename=investor_filename,
    )
    indicator_frame = report_generator.load_indicator_frame(request)
    signal_frame = report_generator.load_signal_frame(request)
    investor_frame = report_generator.load_investor_frame(request)
    stock_info_frame = report_generator.load_stock_info_frame(request)

    report = report_generator.generate_report(
        request=request,
        indicator_frame=indicator_frame,
        signal_frame=signal_frame,
        investor_frame=investor_frame,
        stock_info_frame=stock_info_frame,
    )
    report_date = report.iloc[0]["date"] if not report.empty else "latest"
    report_suffix = str(report_date).replace("-", "")
    saved = report_generator.save_report(f"{symbol}_{report_suffix}.csv", report)
    return {
        "symbol": symbol,
        "rows": len(report),
        "indicator_file": indicator_filename,
        "signal_file": signal_filename,
        "investor_file": investor_filename,
        "saved_path": str(saved.path),
    }


def main() -> None:
    args = _parse_args()
    symbol = args.symbol

    try:
        result = generate_market_report_for_symbol(symbol)
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

    print(result)


if __name__ == "__main__":
    main()
