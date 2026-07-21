from __future__ import annotations

import pandas as pd

from invest_bot.backtest import (
    BACKTEST_STRATEGY_IDS,
    BACKTEST_STRATEGY_SPECS,
    build_run_readiness_gate,
    check_backtest_readiness,
)
from invest_bot.backtest.strategy_registry import DAILY_PRICES_INDICATORS, INVESTOR_DAILY


def _indicator_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2026-01-02", "2026-01-05"],
            "close": [100.0, 101.0],
            "ma_5": [99.0, 100.0],
            "ma_20": [98.0, 99.0],
            "ma_60": [95.0, 96.0],
            "rsi_14": [45.0, 55.0],
            "momentum_20": [3.0, 4.0],
        }
    )


def _investor_frame(date_column: str = "date") -> pd.DataFrame:
    return pd.DataFrame(
        {
            date_column: ["2026-01-02", "2026-01-05"],
            "foreign_net_qty": [1000, 2000],
            "institutional_net_qty": [500, 600],
        }
    )


def test_registry_contains_exact_backtest_strategy_ids_and_contracts() -> None:
    assert BACKTEST_STRATEGY_IDS == (
        "golden-cross",
        "rsi",
        "trend-filter",
        "mean-reversion",
        "disparity",
        "momentum",
        "investor-flow-custom",
    )
    assert set(BACKTEST_STRATEGY_SPECS) == set(BACKTEST_STRATEGY_IDS)

    golden_cross = BACKTEST_STRATEGY_SPECS["golden-cross"]
    assert golden_cross.required_columns[DAILY_PRICES_INDICATORS] == ("date", "close", "ma_5", "ma_20")
    assert golden_cross.derived_fields == ("prev_ma_5", "prev_ma_20")

    investor_flow = BACKTEST_STRATEGY_SPECS["investor-flow-custom"]
    assert investor_flow.required_datasets == (DAILY_PRICES_INDICATORS, INVESTOR_DAILY)
    assert investor_flow.required_columns[DAILY_PRICES_INDICATORS] == ("date", "close", "ma_20")
    assert investor_flow.required_columns[INVESTOR_DAILY] == ("foreign_net_qty", "institutional_net_qty")
    assert investor_flow.date_column_aliases[INVESTOR_DAILY] == ("date", "trade_date")
    assert "investor_source_filename" in investor_flow.provenance_needs


def test_price_strategies_are_ready_from_daily_price_indicators() -> None:
    selected = ["golden-cross", "rsi", "trend-filter", "mean-reversion", "disparity", "momentum"]
    result = check_backtest_readiness(selected, {DAILY_PRICES_INDICATORS: _indicator_frame()})

    assert result.ready_to_run is True
    assert result.unready_strategy_ids == ()
    assert result.blocking_reasons == ()


def test_selected_unready_strategy_blocks_run_with_reasons() -> None:
    gate = build_run_readiness_gate(
        ["rsi", "momentum"],
        {DAILY_PRICES_INDICATORS: _indicator_frame().drop(columns=["momentum_20"])},
    )

    assert gate.can_run is False
    assert gate.readiness.unready_strategy_ids == ("momentum",)
    assert any("momentum: missing columns" in reason and "momentum_20" in reason for reason in gate.blocking_reasons)


def test_investor_flow_requires_date_aligned_investor_daily() -> None:
    datasets = {
        DAILY_PRICES_INDICATORS: _indicator_frame(),
        INVESTOR_DAILY: pd.DataFrame(
            {
                "date": ["2026-01-02"],
                "foreign_net_qty": [1000],
                "institutional_net_qty": [500],
            }
        ),
    }

    result = check_backtest_readiness(["investor-flow-custom"], datasets)

    assert result.ready_to_run is False
    assert result.unready_strategy_ids == ("investor-flow-custom",)
    assert any("not aligned" in reason and "2026-01-05" in reason for reason in result.blocking_reasons)


def test_investor_flow_accepts_trade_date_alias_when_aligned() -> None:
    result = check_backtest_readiness(
        ["investor-flow-custom"],
        {DAILY_PRICES_INDICATORS: _indicator_frame(), INVESTOR_DAILY: _investor_frame("trade_date")},
    )

    assert result.ready_to_run is True
