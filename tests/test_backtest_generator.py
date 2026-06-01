from __future__ import annotations

import pandas as pd

from invest_bot.jobs.generate_backtest import BacktestRequest, GoldenCrossBacktestGenerator
from invest_bot.jobs.run_backtest import run_backtest_for_symbol
from invest_bot.market.storage import CsvStorage
from tests.helpers import make_test_dir


def test_backtest_generator_creates_trade_log_and_summary():
    test_dir = make_test_dir("backtest_generator")
    processed_storage = CsvStorage(test_dir / "processed")
    generator = GoldenCrossBacktestGenerator(processed_storage=processed_storage)

    signal_frame = pd.DataFrame(
        [
            {"date": "2026-04-01", "close": 100, "signal": "hold"},
            {"date": "2026-04-02", "close": 101, "signal": "buy"},
            {"date": "2026-04-03", "close": 103, "signal": "hold"},
            {"date": "2026-04-04", "close": 107, "signal": "sell"},
            {"date": "2026-04-05", "close": 110, "signal": "hold"},
        ]
    )
    processed_storage.save("golden_cross_signals", "005930_backtest.csv", signal_frame)

    loaded = generator.load_signal_frame(
        BacktestRequest(symbol="005930", source_filename="005930_backtest.csv")
    )
    result = generator.run_backtest("005930", loaded)
    trades_saved = generator.save_trades("005930_backtest.csv", result.trades)
    summary_saved = generator.save_summary("005930_backtest.csv", result.summary)

    assert trades_saved.path.exists()
    assert summary_saved.path.exists()
    assert len(result.trades) == 1
    assert result.trades.iloc[0]["entry_date"].strftime("%Y-%m-%d") == "2026-04-03"
    assert result.trades.iloc[0]["exit_date"].strftime("%Y-%m-%d") == "2026-04-05"
    assert result.trades.iloc[0]["exit_reason"] == "sell_signal"
    assert result.summary.iloc[0]["trade_count"] == 1
    assert result.summary.iloc[0]["total_return_pct"] > 0


def test_backtest_generator_closes_open_position_at_final_row():
    test_dir = make_test_dir("backtest_generator_final_close")
    processed_storage = CsvStorage(test_dir / "processed")
    generator = GoldenCrossBacktestGenerator(processed_storage=processed_storage)

    signal_frame = pd.DataFrame(
        [
            {"date": "2026-04-01", "close": 100, "signal": "hold"},
            {"date": "2026-04-02", "close": 101, "signal": "buy"},
            {"date": "2026-04-03", "close": 103, "signal": "hold"},
            {"date": "2026-04-04", "close": 104, "signal": "hold"},
        ]
    )
    processed_storage.save("golden_cross_signals", "005930_final_close.csv", signal_frame)

    loaded = generator.load_signal_frame(
        BacktestRequest(symbol="005930", source_filename="005930_final_close.csv")
    )
    result = generator.run_backtest("005930", loaded)

    assert len(result.trades) == 1
    assert result.trades.iloc[0]["exit_reason"] == "final_close"
    assert result.summary.iloc[0]["trade_count"] == 1


def test_run_backtest_for_symbol_uses_latest_signal_file():
    test_dir = make_test_dir("backtest_runner")
    processed_storage = CsvStorage(test_dir / "processed")
    generator = GoldenCrossBacktestGenerator(processed_storage=processed_storage)

    processed_storage.save(
        "golden_cross_signals",
        "005930_backtest.csv",
        pd.DataFrame(
            [
                {"date": "2026-04-01", "close": 100, "signal": "hold"},
                {"date": "2026-04-02", "close": 101, "signal": "buy"},
                {"date": "2026-04-03", "close": 103, "signal": "hold"},
                {"date": "2026-04-04", "close": 107, "signal": "sell"},
                {"date": "2026-04-05", "close": 110, "signal": "hold"},
            ]
        ),
    )

    result = run_backtest_for_symbol("005930", generator=generator)

    assert result["symbol"] == "005930"
    assert result["signal_rows"] == 5
    assert result["trade_count"] == 1
