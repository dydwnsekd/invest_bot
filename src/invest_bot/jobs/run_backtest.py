from __future__ import annotations

import argparse
from invest_bot.jobs.generate_backtest import BacktestRequest, GoldenCrossBacktestGenerator


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a draft backtest from golden cross signal CSV files.")
    parser.add_argument("symbol", nargs="?", default="005930", help="Stock symbol to backtest.")
    return parser.parse_args()


def run_backtest_for_symbol(
    symbol: str,
    generator: GoldenCrossBacktestGenerator | None = None,
) -> dict[str, str | int | float]:
    backtest_generator = generator or GoldenCrossBacktestGenerator()
    source_filename = backtest_generator.processed_storage.latest_filename("golden_cross_signals", symbol)
    if source_filename is None:
        raise FileNotFoundError(f"No golden_cross_signals dataset found for symbol '{symbol}'. Run signal generation first.")
    request = BacktestRequest(symbol=symbol, source_filename=source_filename)
    signal_frame = backtest_generator.load_signal_frame(request)
    result = backtest_generator.run_backtest(symbol, signal_frame)
    trades_saved = backtest_generator.save_trades(request.source_filename, result.trades)
    summary_saved = backtest_generator.save_summary(request.source_filename, result.summary)
    summary_row = result.summary.iloc[0].to_dict()
    return {
        "symbol": symbol,
        "source_file": source_filename,
        "signal_rows": len(signal_frame),
        "trade_count": int(summary_row["trade_count"]),
        "total_return_pct": float(summary_row["total_return_pct"]),
        "win_rate_pct": float(summary_row["win_rate_pct"]),
        "trades_saved_path": str(trades_saved.path),
        "summary_saved_path": str(summary_saved.path),
    }


def main() -> None:
    args = _parse_args()
    symbol = args.symbol
    try:
        result = run_backtest_for_symbol(symbol)
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
                    "4. python scripts/run_backtest.py <symbol>",
                ]
            )
        ) from error

    print(result)


if __name__ == "__main__":
    main()
