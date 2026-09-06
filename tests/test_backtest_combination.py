from __future__ import annotations

import pandas as pd
import pytest

from invest_bot.backtest import combine_strategy_signal_rows, resolve_backtest_combination_settings


def _signals(values: list[str], *, dates: list[str] | None = None) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": dates or ["2026-04-01", "2026-04-02", "2026-04-03"],
            "close": [100.0 + index for index in range(len(values))],
            "signal": values,
        }
    )


def test_and_or_and_weighted_combination_handle_agreement_and_conflicts() -> None:
    frames = {
        "rsi": _signals(["buy", "sell", "buy"]),
        "momentum": _signals(["buy", "sell", "hold"]),
    }

    and_rows = combine_strategy_signal_rows(frames, resolve_backtest_combination_settings(["rsi", "momentum"], "and"))
    or_rows = combine_strategy_signal_rows(frames, resolve_backtest_combination_settings(["rsi", "momentum"], "or"))
    weighted_rows = combine_strategy_signal_rows(
        frames,
        resolve_backtest_combination_settings(["rsi", "momentum"], "weighted", {"rsi": 2.0, "momentum": 1.0}),
    )

    assert and_rows["signal"].tolist() == ["buy", "sell", "hold"]
    assert or_rows["signal"].tolist() == ["buy", "sell", "buy"]
    assert weighted_rows["signal"].tolist() == ["buy", "sell", "buy"]
    assert weighted_rows["combination_score"].tolist() == [3.0, -3.0, 2.0]
    assert "rsi: buy" in weighted_rows.iloc[0]["component_signals"]


def test_weighted_tie_and_missing_common_dates_are_explained() -> None:
    frames = {
        "rsi": _signals(["buy", "hold", "sell"]),
        "momentum": _signals(["sell", "hold", "buy"]),
    }
    settings = resolve_backtest_combination_settings(["rsi", "momentum"], "weighted")
    rows = combine_strategy_signal_rows(frames, settings)

    assert rows["signal"].tolist() == ["hold", "hold", "hold"]
    assert rows["combination_score"].tolist() == [0.0, 0.0, 0.0]

    with pytest.raises(ValueError, match="공통 거래일"):
        combine_strategy_signal_rows(
            {"rsi": _signals(["buy"], dates=["2026-04-01"]), "momentum": _signals(["buy"], dates=["2026-04-02"])},
            settings,
        )


@pytest.mark.parametrize(
    ("strategy_ids", "mode", "weights", "message"),
    [
        (["rsi"], "and", None, "두 개 이상"),
        (["rsi", "momentum"], "unknown", None, "지원하지 않는"),
        (["rsi", "momentum"], "weighted", {"rsi": 0.0}, "0.1~3.0"),
    ],
)
def test_combination_settings_validate_selected_strategies_and_weights(
    strategy_ids: list[str], mode: str, weights: dict[str, float] | None, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        resolve_backtest_combination_settings(strategy_ids, mode, weights)
