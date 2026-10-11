from __future__ import annotations

import pandas as pd
import pytest

from invest_bot.backtest import (
    BacktestDataReadinessError,
    DEFAULT_BACKTEST_RUNNER,
    GOLDEN_CROSS_SIGNALS,
    build_daily_mark_to_market_equity_curve,
    build_strategy_signal_rows,
    check_backtest_readiness,
    combine_strategy_signal_rows,
    resolve_backtest_combination_settings,
)
from invest_bot.backtest import adapters
from invest_bot.backtest.dates import duplicate_trading_date_reason
from invest_bot.backtest.strategy_registry import DAILY_PRICES_INDICATORS, INVESTOR_DAILY


DATE_PAIRS = [
    pytest.param("2026-04-03", "2026-04-03", id="identical-date"),
    pytest.param("2026-04-03", pd.Timestamp("2026-04-03"), id="string-timestamp"),
    pytest.param("2026-04-03 09:00:00", "2026-04-03 15:30:00", id="intraday"),
    pytest.param("2026-04-03", "2026-04-03 15:30:00", id="mixed-string-format"),
]


def _rows(dates: list[object], *, conflicting: bool = True) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dates, dtype=object),
            "close": [100.0] * (len(dates) - 1) + [200.0 if conflicting else 100.0],
            "signal": ["buy"] * (len(dates) - 1) + ["sell" if conflicting else "buy"],
            "rsi_14": [25.0] * len(dates),
            "ma_5": [101.0] * len(dates),
            "ma_20": [100.0] * len(dates),
            "ma_60": [99.0] * len(dates),
            "momentum_20": [12.0] * len(dates),
        }
    )


@pytest.mark.parametrize(("first", "second"), DATE_PAIRS)
@pytest.mark.parametrize("conflicting", [False, True], ids=["equal-rows", "conflicting-rows"])
@pytest.mark.parametrize("boundary", ["readiness", "saved-adapter", "runner", "curve", "combination"])
def test_duplicate_calendar_dates_are_rejected_without_mutating_input(
    first: object, second: object, conflicting: bool, boundary: str
) -> None:
    frame = _rows([first, second], conflicting=conflicting)
    before = frame.copy(deep=True)
    if boundary == "readiness":
        result = check_backtest_readiness(["rsi"], {DAILY_PRICES_INDICATORS: frame})
        assert not result.ready_to_run
        reason = "; ".join(result.blocking_reasons)
        assert DAILY_PRICES_INDICATORS in reason
        assert "duplicate trading dates" in reason
        assert "2026-04-03" in reason
    else:
        with pytest.raises(ValueError, match="duplicate trading dates.*2026-04-03"):
            if boundary == "saved-adapter":
                build_strategy_signal_rows("golden-cross", {GOLDEN_CROSS_SIGNALS: frame})
            elif boundary == "runner":
                DEFAULT_BACKTEST_RUNNER.run("005930", frame)
            elif boundary == "curve":
                build_daily_mark_to_market_equity_curve(frame, pd.DataFrame())
            else:
                settings = resolve_backtest_combination_settings(["rsi", "momentum"])
                combine_strategy_signal_rows({"rsi": frame, "momentum": frame.copy()}, settings)
    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize("strategy_id", [
    "golden-cross", "rsi", "trend-filter", "mean-reversion", "disparity", "momentum", "investor-flow-custom",
])
def test_indicator_duplicates_block_before_strategy_preparation(monkeypatch: pytest.MonkeyPatch, strategy_id: str) -> None:
    def unexpected_preparation(*_args: object) -> None:
        pytest.fail("duplicate inputs reached strategy preparation")

    monkeypatch.setattr(adapters, "_prepare_price_frame", unexpected_preparation)
    frame = _rows(["2026-04-03", "2026-04-03"])
    investor = pd.DataFrame({"date": ["2026-04-03"], "foreign_net_qty": [1.0], "institutional_net_qty": [1.0]})
    with pytest.raises(BacktestDataReadinessError, match="duplicate trading dates"):
        build_strategy_signal_rows(strategy_id, {DAILY_PRICES_INDICATORS: frame, INVESTOR_DAILY: investor})


@pytest.mark.parametrize("date_column", ["date", "trade_date"])
@pytest.mark.parametrize(("first", "second"), DATE_PAIRS)
def test_normalized_investor_duplicates_block_before_merge(date_column: str, first: object, second: object) -> None:
    price = _rows(["2026-04-03"])
    investor = pd.DataFrame({date_column: [first, second], "foreign_net_qty": [1.0, -1.0], "institutional_net_qty": [1.0, -1.0]})
    before = investor.copy(deep=True)
    datasets = {DAILY_PRICES_INDICATORS: price, INVESTOR_DAILY: investor}
    readiness = check_backtest_readiness(["investor-flow-custom"], datasets)
    assert not readiness.ready_to_run
    assert "investor_daily has duplicate trading dates: 2026-04-03" in "; ".join(readiness.blocking_reasons)
    with pytest.raises(BacktestDataReadinessError, match="investor_daily has duplicate trading dates"):
        build_strategy_signal_rows("investor-flow-custom", datasets)
    pd.testing.assert_frame_equal(investor, before)


@pytest.mark.parametrize("boundary", ["curve", "combination"])
def test_duplicate_date_cannot_be_hidden_by_invalid_close_filter(boundary: str) -> None:
    frame = _rows(["2026-04-03", "2026-04-03"])
    frame.loc[1, "close"] = None
    with pytest.raises(ValueError, match="duplicate trading dates"):
        if boundary == "curve":
            build_daily_mark_to_market_equity_curve(frame, pd.DataFrame())
        else:
            settings = resolve_backtest_combination_settings(["rsi", "momentum"])
            combine_strategy_signal_rows({"rsi": frame, "momentum": frame.copy()}, settings)


def test_duplicate_exit_date_cannot_produce_zero_trade_return_and_100_percent_summary() -> None:
    frame = _rows(["2026-04-01", "2026-04-02", "2026-04-03", "2026-04-03"])
    frame["signal"] = ["buy", "sell", "hold", "hold"]
    with pytest.raises(ValueError, match="duplicate trading dates.*2026-04-03"):
        DEFAULT_BACKTEST_RUNNER.run("005930", frame)


def test_unique_unsorted_inputs_and_separate_symbols_preserve_existing_results() -> None:
    frame = _rows(["2026-04-06", "2026-04-03"], conflicting=False)
    frame["signal"] = "hold"
    before = frame.copy(deep=True)
    for symbol in ["005930", "000660"]:
        result = DEFAULT_BACKTEST_RUNNER.run(symbol, frame)
        assert result.summary.iloc[0]["symbol"] == symbol
        assert result.summary.iloc[0]["total_return_pct"] == 0.0
    settings = resolve_backtest_combination_settings(["rsi", "momentum"])
    combined = combine_strategy_signal_rows({"rsi": frame, "momentum": frame.copy()}, settings)
    assert combined["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-04-03", "2026-04-06"]
    pd.testing.assert_frame_equal(frame, before)


def test_nat_and_empty_treatment_is_not_replaced_by_duplicate_rejection() -> None:
    frame = _rows([None, "invalid", "2026-04-03"])
    frame["signal"] = "hold"
    assert check_backtest_readiness(["rsi"], {DAILY_PRICES_INDICATORS: frame}).ready_to_run
    saved = build_strategy_signal_rows("golden-cross", {GOLDEN_CROSS_SIGNALS: frame})
    assert saved["date"].isna().sum() == 2
    result = DEFAULT_BACKTEST_RUNNER.run("005930", frame)
    assert result.summary.iloc[0]["source_rows"] == 3
    curve = build_daily_mark_to_market_equity_curve(frame, result.trades)
    assert len(curve) == 1
    settings = resolve_backtest_combination_settings(["rsi", "momentum"])
    assert len(combine_strategy_signal_rows({"rsi": frame, "momentum": frame.copy()}, settings)) == 1
    empty = frame.iloc[:0]
    assert not check_backtest_readiness(["rsi"], {DAILY_PRICES_INDICATORS: empty}).ready_to_run
    assert build_strategy_signal_rows("golden-cross", {GOLDEN_CROSS_SIGNALS: empty}).empty
    assert DEFAULT_BACKTEST_RUNNER.run("005930", empty).trades.empty
    assert build_daily_mark_to_market_equity_curve(empty, pd.DataFrame()).empty


def test_investor_alignment_preserves_weekend_extras_and_missing_date_block() -> None:
    price = _rows(["2026-04-03", "2026-04-06"])
    investor = pd.DataFrame({"trade_date": ["2026-04-03", "2026-04-04", "2026-04-06"],
                             "foreign_net_qty": [1.0, 1.0, 1.0], "institutional_net_qty": [1.0, 1.0, 1.0]})
    datasets = {DAILY_PRICES_INDICATORS: price, INVESTOR_DAILY: investor}
    assert check_backtest_readiness(["investor-flow-custom"], datasets).ready_to_run
    assert len(build_strategy_signal_rows("investor-flow-custom", datasets)) == 2
    datasets[INVESTOR_DAILY] = investor.iloc[:2]
    readiness = check_backtest_readiness(["investor-flow-custom"], datasets)
    assert not readiness.ready_to_run
    assert "missing investor flow for 2026-04-06" in "; ".join(readiness.blocking_reasons)


def test_unclosed_mark_to_market_position_is_not_forced_to_realized_return() -> None:
    prices = _rows(["2026-04-01", "2026-04-02", "2026-04-03"])
    prices["close"] = [100.0, 100.0, 80.0]
    trades = pd.DataFrame({"entry_date": ["2026-04-02"], "entry_price": [100.0],
                           "exit_date": ["2026-04-06"], "exit_price": [120.0]})
    curve = build_daily_mark_to_market_equity_curve(prices, trades, initial_equity=1.0)
    assert curve["equity"].tolist() == [1.0, 1.0, 0.8]
    assert curve.iloc[-1]["position_state"] == "보유"
    assert curve.iloc[-1]["equity_return_pct"] == pytest.approx(-20.0)


@pytest.mark.parametrize(("dates", "expected_date"), [
    pytest.param(["2026-04-03 00:30:00+09:00", "2026-04-03 23:30:00-04:00"], "2026-04-03",
                 id="same-local-date-different-utc-dates"),
    pytest.param(["2026-04-03 00:30:00+09:00", "2026-04-02 11:30:00-04:00"], None,
                 id="different-local-dates-same-instant"),
])
def test_duplicate_check_keeps_local_calendar_dates_with_mixed_offsets(
    dates: list[str], expected_date: str | None
) -> None:
    frame = _rows(dates)
    before = frame.copy(deep=True)
    reason = duplicate_trading_date_reason(frame, source="offset rows")
    if expected_date is None:
        assert reason is None
    else:
        assert reason is not None
        assert f"duplicate trading dates: {expected_date}" in reason
    pd.testing.assert_frame_equal(frame, before)
