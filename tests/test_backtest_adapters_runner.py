from __future__ import annotations

import pandas as pd
import pytest

from invest_bot.backtest import (
    BacktestDataReadinessError,
    DEFAULT_BACKTEST_RUNNER,
    GOLDEN_CROSS_SIGNALS,
    build_strategy_signal_rows,
)
from invest_bot.backtest.strategy_registry import DAILY_PRICES_INDICATORS, INVESTOR_DAILY


def test_golden_cross_adapter_builds_normalized_rows_from_indicator_frame() -> None:
    frame = pd.DataFrame(
        [
            {"date": "2026-04-01", "close": 100, "ma_5": 98, "ma_20": 99},
            {"date": "2026-04-02", "close": 101, "ma_5": 100, "ma_20": 99},
            {"date": "2026-04-03", "close": 102, "ma_5": 101, "ma_20": 100},
            {"date": "2026-04-04", "close": 99, "ma_5": 98, "ma_20": 100},
        ]
    )

    rows = build_strategy_signal_rows("golden-cross", {DAILY_PRICES_INDICATORS: frame})

    assert list(rows[["signal", "strategy_id"]].itertuples(index=False, name=None)) == [
        ("hold", "golden-cross"),
        ("buy", "golden-cross"),
        ("hold", "golden-cross"),
        ("sell", "golden-cross"),
    ]
    assert rows.iloc[1]["strategy_name"] == "Golden Cross"
    assert rows.iloc[1]["prev_ma_5"] == 98
    assert rows.iloc[1]["prev_ma_20"] == 99
    assert "crossed above" in rows.iloc[1]["signal_reason"]
    assert "crossed below" in rows.iloc[3]["signal_reason"]


def test_golden_cross_adapter_accepts_existing_signal_frame_compatibility() -> None:
    rows = build_strategy_signal_rows(
        "golden-cross",
        {
            GOLDEN_CROSS_SIGNALS: pd.DataFrame(
                [
                    {"date": "2026-04-02", "close": 101, "signal": "BUY", "signal_reason": "upward cross", "ma_5": 100},
                    {"date": "2026-04-03", "close": 102, "signal": "hold", "signal_reason": "none", "ma_5": 101},
                ]
            )
        },
    )

    assert list(rows["signal"]) == ["buy", "hold"]
    assert list(rows["strategy_id"]) == ["golden-cross", "golden-cross"]
    assert list(rows["close"]) == [101, 102]


def test_golden_cross_adapter_accepts_empty_existing_signal_frame() -> None:
    rows = build_strategy_signal_rows(
        "golden-cross",
        {
            GOLDEN_CROSS_SIGNALS: pd.DataFrame(columns=["date", "close", "signal"]),
        },
    )

    assert rows.empty
    assert list(rows.columns) == ["date", "close", "signal", "strategy_id", "strategy_name", "signal_reason"]


@pytest.mark.parametrize(
    ("strategy_id", "column", "values", "expected_signals"),
    [
        ("rsi", "rsi_14", [25.0, 50.0, 75.0], ["buy", "hold", "sell"]),
        ("momentum", "momentum_20", [12.0, 0.0, -12.0], ["buy", "hold", "sell"]),
    ],
)
def test_threshold_based_adapters_emit_expected_signals(
    strategy_id: str,
    column: str,
    values: list[float],
    expected_signals: list[str],
) -> None:
    frame = pd.DataFrame(
        {
            "date": ["2026-04-01", "2026-04-02", "2026-04-03"],
            "close": [100.0, 101.0, 102.0],
            column: values,
        }
    )

    rows = build_strategy_signal_rows(strategy_id, {DAILY_PRICES_INDICATORS: frame})

    assert list(rows["signal"]) == expected_signals
    assert list(rows["strategy_id"].unique()) == [strategy_id]
    assert column in rows.columns


def test_trend_filter_adapter_uses_prev_close_derivation() -> None:
    frame = pd.DataFrame(
        [
            {"date": "2026-04-01", "close": 100, "ma_60": 99},
            {"date": "2026-04-02", "close": 103, "ma_60": 100},
            {"date": "2026-04-03", "close": 95, "ma_60": 99},
        ]
    )

    rows = build_strategy_signal_rows("trend-filter", {DAILY_PRICES_INDICATORS: frame})

    assert rows.iloc[0]["signal"] == "hold"
    assert rows.iloc[0]["signal_reason"] == "Missing indicators: prev_close"
    assert rows.iloc[1]["prev_close"] == 100
    assert rows.iloc[1]["signal"] == "buy"
    assert rows.iloc[2]["signal"] == "sell"


@pytest.mark.parametrize(
    ("strategy_id", "close_values", "expected_signals", "derived_column"),
    [
        ("mean-reversion", [97.0, 100.0, 103.0], ["buy", "hold", "sell"], "price_to_baseline_ratio"),
        ("disparity", [97.0, 100.0, 103.0], ["buy", "hold", "sell"], "disparity_pct"),
    ],
)
def test_ma20_based_adapters_emit_expected_signals(
    strategy_id: str,
    close_values: list[float],
    expected_signals: list[str],
    derived_column: str,
) -> None:
    frame = pd.DataFrame(
        {
            "date": ["2026-04-01", "2026-04-02", "2026-04-03"],
            "close": close_values,
            "ma_20": [100.0, 100.0, 100.0],
        }
    )

    rows = build_strategy_signal_rows(strategy_id, {DAILY_PRICES_INDICATORS: frame})

    assert list(rows["signal"]) == expected_signals
    assert derived_column in rows.columns


def test_investor_flow_adapter_blocks_on_unaligned_dates() -> None:
    price_frame = pd.DataFrame(
        {
            "date": ["2026-04-01", "2026-04-02"],
            "close": [101.0, 99.0],
            "ma_20": [100.0, 100.0],
        }
    )
    investor_frame = pd.DataFrame(
        {
            "trade_date": ["2026-04-01"],
            "foreign_net_qty": [1000.0],
            "institutional_net_qty": [500.0],
        }
    )

    with pytest.raises(BacktestDataReadinessError) as error:
        build_strategy_signal_rows(
            "investor-flow-custom",
            {DAILY_PRICES_INDICATORS: price_frame, INVESTOR_DAILY: investor_frame},
        )

    assert "not aligned" in str(error.value)
    assert "2026-04-02" in str(error.value)


def test_investor_flow_adapter_emits_buy_hold_sell_from_aligned_frames() -> None:
    price_frame = pd.DataFrame(
        {
            "date": ["2026-04-01", "2026-04-02", "2026-04-03"],
            "close": [101.0, 100.0, 99.0],
            "ma_20": [100.0, 100.0, 100.0],
        }
    )
    investor_frame = pd.DataFrame(
        {
            "trade_date": ["2026-04-01", "2026-04-02", "2026-04-03"],
            "foreign_net_qty": [1000.0, 1000.0, -1000.0],
            "institutional_net_qty": [500.0, -300.0, -500.0],
        }
    )

    rows = build_strategy_signal_rows(
        "investor-flow-custom",
        {DAILY_PRICES_INDICATORS: price_frame, INVESTOR_DAILY: investor_frame},
    )

    assert list(rows["signal"]) == ["buy", "hold", "sell"]
    assert rows.iloc[0]["strategy_name"] == "Investor Flow Custom"
    assert "foreign_net_qty" in rows.columns
    assert "institutional_net_qty" in rows.columns


def test_runner_preserves_next_day_close_semantics_and_final_close() -> None:
    rows = pd.DataFrame(
        [
            {"date": "2026-04-01", "close": 100, "signal": "hold", "signal_reason": "n/a", "strategy_id": "golden-cross", "strategy_name": "Golden Cross"},
            {"date": "2026-04-02", "close": 101, "signal": "buy", "signal_reason": "buy", "strategy_id": "golden-cross", "strategy_name": "Golden Cross"},
            {"date": "2026-04-03", "close": 103, "signal": "hold", "signal_reason": "hold", "strategy_id": "golden-cross", "strategy_name": "Golden Cross"},
            {"date": "2026-04-04", "close": 107, "signal": "sell", "signal_reason": "sell", "strategy_id": "golden-cross", "strategy_name": "Golden Cross"},
            {"date": "2026-04-05", "close": 110, "signal": "hold", "signal_reason": "hold", "strategy_id": "golden-cross", "strategy_name": "Golden Cross"},
            {"date": "2026-04-06", "close": 111, "signal": "buy", "signal_reason": "buy", "strategy_id": "golden-cross", "strategy_name": "Golden Cross"},
            {"date": "2026-04-07", "close": 112, "signal": "hold", "signal_reason": "hold", "strategy_id": "golden-cross", "strategy_name": "Golden Cross"},
        ]
    )

    result = DEFAULT_BACKTEST_RUNNER.run("005930", rows)

    assert len(result.trades) == 2
    assert result.trades.iloc[0]["entry_date"].strftime("%Y-%m-%d") == "2026-04-03"
    assert result.trades.iloc[0]["exit_date"].strftime("%Y-%m-%d") == "2026-04-05"
    assert result.trades.iloc[0]["exit_reason"] == "sell_signal"
    assert result.trades.iloc[1]["entry_date"].strftime("%Y-%m-%d") == "2026-04-07"
    assert result.trades.iloc[1]["exit_date"].strftime("%Y-%m-%d") == "2026-04-07"
    assert result.trades.iloc[1]["exit_reason"] == "final_close"
    assert result.summary.iloc[0]["strategy_id"] == "golden-cross"
    assert result.summary.iloc[0]["trade_count"] == 2
