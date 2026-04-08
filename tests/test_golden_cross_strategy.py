from __future__ import annotations

import pandas as pd

from invest_bot.strategy import GoldenCrossStrategy, Signal


def test_golden_cross_strategy_returns_buy_signal_on_upward_cross():
    strategy = GoldenCrossStrategy()

    result = strategy.evaluate(
        {
            "prev_ma_5": 98.0,
            "prev_ma_20": 100.0,
            "ma_5": 101.0,
            "ma_20": 100.0,
        }
    )

    assert result.signal is Signal.BUY
    assert "crossed above" in result.reason


def test_golden_cross_strategy_returns_sell_signal_on_downward_cross():
    strategy = GoldenCrossStrategy()

    result = strategy.evaluate(
        {
            "prev_ma_5": 102.0,
            "prev_ma_20": 100.0,
            "ma_5": 99.0,
            "ma_20": 100.0,
        }
    )

    assert result.signal is Signal.SELL
    assert "crossed below" in result.reason


def test_golden_cross_strategy_returns_hold_when_no_cross_happens():
    strategy = GoldenCrossStrategy()

    result = strategy.evaluate(
        {
            "prev_ma_5": 99.0,
            "prev_ma_20": 100.0,
            "ma_5": 99.5,
            "ma_20": 100.0,
        }
    )

    assert result.signal is Signal.HOLD


def test_golden_cross_strategy_can_evaluate_indicator_frame():
    strategy = GoldenCrossStrategy()
    frame = pd.DataFrame(
        [
            {"date": "2026-04-01", "ma_5": 98.0, "ma_20": 100.0},
            {"date": "2026-04-02", "ma_5": 101.0, "ma_20": 100.0},
        ]
    )

    result = strategy.evaluate_frame(frame)

    assert result.signal is Signal.BUY
