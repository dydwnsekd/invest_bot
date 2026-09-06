from __future__ import annotations

import pandas as pd
import pytest

from invest_bot.backtest import (
    build_strategy_signal_rows,
    default_backtest_parameters,
    resolve_backtest_parameters,
)
from invest_bot.backtest.strategy_registry import DAILY_PRICES_INDICATORS


def test_default_parameters_preserve_existing_rsi_signal_rows() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2026-04-01", "2026-04-02", "2026-04-03"],
            "close": [100.0, 101.0, 102.0],
            "rsi_14": [25.0, 50.0, 75.0],
        }
    )

    original = build_strategy_signal_rows("rsi", {DAILY_PRICES_INDICATORS: frame})
    with_defaults = build_strategy_signal_rows(
        "rsi",
        {DAILY_PRICES_INDICATORS: frame},
        parameters=default_backtest_parameters("rsi"),
    )

    pd.testing.assert_frame_equal(original, with_defaults)


def test_custom_rsi_parameters_change_signal_within_allowed_range() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2026-04-01", "2026-04-02", "2026-04-03"],
            "close": [100.0, 101.0, 102.0],
            "rsi_14": [35.0, 50.0, 65.0],
        }
    )

    rows = build_strategy_signal_rows(
        "rsi",
        {DAILY_PRICES_INDICATORS: frame},
        parameters={"buy_threshold": 40, "sell_threshold": 60},
    )

    assert rows["signal"].tolist() == ["buy", "hold", "sell"]
    assert "40.00" in rows.iloc[0]["signal_reason"]
    assert "60.00" in rows.iloc[-1]["signal_reason"]


@pytest.mark.parametrize(
    ("strategy_id", "values", "message"),
    [
        ("rsi", {"buy_threshold": None}, "값을 입력"),
        ("rsi", {"buy_threshold": 50, "sell_threshold": 60}, "범위"),
        ("golden-cross", {"short_window": 5.5}, "정수"),
        ("golden-cross", {"short_window": 20, "long_window": 10}, "단기 이동평균 기간은 장기 이동평균 기간보다 짧아야"),
    ],
)
def test_parameter_validation_rejects_missing_out_of_range_and_reversed_values(
    strategy_id: str,
    values: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        resolve_backtest_parameters(strategy_id, values)
