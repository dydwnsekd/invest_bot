from __future__ import annotations

import json
from datetime import UTC, datetime

import pandas as pd

from invest_bot.backtest import DEFAULT_BACKTEST_RUNNER
from invest_bot.jobs.generate_backtest import BacktestRequest, GoldenCrossBacktestGenerator
from invest_bot.jobs.run_backtest import run_backtest_for_symbol
from invest_bot.market.storage import CsvStorage
from tests.helpers import make_test_dir


def test_backtest_generator_persists_symbol_first_files_with_run_identity_and_provenance() -> None:
    test_dir = make_test_dir("backtest_persistence_generator")
    processed_storage = CsvStorage(test_dir / "processed")
    fixed_now = lambda: datetime(2026, 7, 20, 1, 2, 3, tzinfo=UTC)
    generator = GoldenCrossBacktestGenerator(processed_storage=processed_storage, now_fn=fixed_now)

    signal_frame = pd.DataFrame(
        [
            {"date": "2026-04-01", "close": 100, "signal": "hold", "signal_reason": "n/a"},
            {"date": "2026-04-02", "close": 101, "signal": "buy", "signal_reason": "buy"},
            {"date": "2026-04-03", "close": 103, "signal": "hold", "signal_reason": "hold"},
            {"date": "2026-04-04", "close": 107, "signal": "sell", "signal_reason": "sell"},
            {"date": "2026-04-05", "close": 110, "signal": "hold", "signal_reason": "hold"},
        ]
    )
    processed_storage.save("golden_cross_signals", "005930_20260305.csv", signal_frame)

    request = BacktestRequest(
        symbol="005930",
        source_filename="005930_20260305.csv",
        indicator_filename="005930_20260305.csv",
        investor_filename="005930_20260305.csv",
        price_filename="005930_20260301_20260305.csv",
    )
    loaded = generator.load_signal_frame(request)
    result = generator.run_backtest("005930", loaded)
    trades_saved = generator.save_trades(request.source_filename, result.trades)
    summary_saved = generator.save_summary(request.source_filename, result.summary)

    assert trades_saved.path.name == "005930_golden-cross_20260720T010203Z_backtest_trades.csv"
    assert summary_saved.path.name == "005930_golden-cross_20260720T010203Z_backtest_summary.csv"

    assert list(result.trades["run_group_id"].unique()) == ["backtest_group_20260720T010203Z"]
    assert list(result.trades["run_id"].unique()) == ["005930_golden-cross_20260720T010203Z"]
    assert list(result.trades["symbol"].unique()) == ["005930"]
    assert list(result.trades["strategy_id"].unique()) == ["golden-cross"]
    assert list(result.trades["strategy_name"].unique()) == ["Golden Cross"]
    assert list(result.trades["output_type"].unique()) == ["backtest_trades"]

    summary_row = result.summary.iloc[0].to_dict()
    assert summary_row["run_group_id"] == "backtest_group_20260720T010203Z"
    assert summary_row["run_id"] == "005930_golden-cross_20260720T010203Z"
    assert summary_row["output_type"] == "backtest_summary"
    assert summary_row["indicator_source_dataset"] == "daily_prices_indicators"
    assert summary_row["indicator_source_filename"] == "005930_20260305.csv"
    assert summary_row["signal_source_dataset"] == "golden_cross_signals"
    assert summary_row["signal_source_filename"] == "005930_20260305.csv"
    assert summary_row["investor_source_dataset"] == "investor_daily"
    assert summary_row["investor_source_filename"] == "005930_20260305.csv"
    assert summary_row["price_source_dataset"] == "daily_prices"
    assert summary_row["price_source_filename"] == "005930_20260301_20260305.csv"
    assert json.loads(summary_row["input_sources_json"]) == {
        "indicator": {"dataset": "daily_prices_indicators", "filename": "005930_20260305.csv"},
        "investor": {"dataset": "investor_daily", "filename": "005930_20260305.csv"},
        "price": {"dataset": "daily_prices", "filename": "005930_20260301_20260305.csv"},
        "signal": {"dataset": "golden_cross_signals", "filename": "005930_20260305.csv"},
    }


def test_run_backtest_for_symbol_does_not_persist_false_default_provenance() -> None:
    test_dir = make_test_dir("backtest_persistence_default_cli_path")
    processed_storage = CsvStorage(test_dir / "processed")
    fixed_now = lambda: datetime(2026, 7, 20, 6, 7, 8, tzinfo=UTC)
    generator = GoldenCrossBacktestGenerator(processed_storage=processed_storage, now_fn=fixed_now)

    processed_storage.save(
        "golden_cross_signals",
        "005930_cli_path.csv",
        pd.DataFrame(
            [
                {"date": "2026-04-01", "close": 100, "signal": "hold"},
                {"date": "2026-04-02", "close": 101, "signal": "buy"},
                {"date": "2026-04-03", "close": 103, "signal": "hold"},
                {"date": "2026-04-04", "close": 107, "signal": "sell"},
            ]
        ),
    )

    result = run_backtest_for_symbol("005930", generator=generator)
    summary_frame = pd.read_csv(result["summary_saved_path"])
    summary_row = summary_frame.iloc[0]

    assert summary_row["signal_source_dataset"] == "golden_cross_signals"
    assert summary_row["signal_source_filename"] == "005930_cli_path.csv"
    assert pd.isna(summary_row["indicator_source_dataset"])
    assert pd.isna(summary_row["indicator_source_filename"])
    assert pd.isna(summary_row["investor_source_dataset"])
    assert pd.isna(summary_row["investor_source_filename"])
    assert pd.isna(summary_row["price_source_dataset"])
    assert pd.isna(summary_row["price_source_filename"])
    assert json.loads(summary_row["input_sources_json"]) == {
        "indicator": {"dataset": None, "filename": None},
        "investor": {"dataset": None, "filename": None},
        "price": {"dataset": None, "filename": None},
        "signal": {"dataset": "golden_cross_signals", "filename": "005930_cli_path.csv"},
    }


def test_backtest_save_helpers_preserve_old_api_and_reuse_one_run_identity() -> None:
    test_dir = make_test_dir("backtest_persistence_compat")
    processed_storage = CsvStorage(test_dir / "processed")
    fixed_now = lambda: datetime(2026, 7, 20, 4, 5, 6, tzinfo=UTC)
    generator = GoldenCrossBacktestGenerator(processed_storage=processed_storage, now_fn=fixed_now)

    rows = pd.DataFrame(
        [
            {"date": "2026-04-01", "close": 100, "signal": "hold", "signal_reason": "n/a", "strategy_id": "golden-cross", "strategy_name": "Golden Cross"},
            {"date": "2026-04-02", "close": 101, "signal": "buy", "signal_reason": "buy", "strategy_id": "golden-cross", "strategy_name": "Golden Cross"},
            {"date": "2026-04-03", "close": 103, "signal": "hold", "signal_reason": "hold", "strategy_id": "golden-cross", "strategy_name": "Golden Cross"},
            {"date": "2026-04-04", "close": 107, "signal": "sell", "signal_reason": "sell", "strategy_id": "golden-cross", "strategy_name": "Golden Cross"},
            {"date": "2026-04-05", "close": 110, "signal": "hold", "signal_reason": "hold", "strategy_id": "golden-cross", "strategy_name": "Golden Cross"},
        ]
    )
    raw_result = DEFAULT_BACKTEST_RUNNER.run("005930", rows)

    trades_saved = generator.save_trades("005930_20260305.csv", raw_result.trades)
    summary_saved = generator.save_summary("005930_20260305.csv", raw_result.summary)

    assert trades_saved.path.name == "005930_golden-cross_20260720T040506Z_backtest_trades.csv"
    assert summary_saved.path.name == "005930_golden-cross_20260720T040506Z_backtest_summary.csv"

    trades_frame = pd.read_csv(trades_saved.path)
    summary_frame = pd.read_csv(summary_saved.path)

    assert list(trades_frame["run_id"].unique()) == ["005930_golden-cross_20260720T040506Z"]
    assert list(summary_frame["run_id"].unique()) == ["005930_golden-cross_20260720T040506Z"]
    assert summary_frame.iloc[0]["indicator_source_dataset"] == "daily_prices_indicators"
    assert summary_frame.iloc[0]["signal_source_dataset"] == "golden_cross_signals"
