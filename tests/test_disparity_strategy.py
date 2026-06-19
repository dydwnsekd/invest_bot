from math import nan

from invest_bot.strategy import DisparityStrategy, Signal


def test_disparity_strategy_returns_buy_signal_below_buy_threshold():
    strategy = DisparityStrategy()

    result = strategy.evaluate({"close": 97.0, "ma_20": 100.0})

    assert result.signal is Signal.BUY
    assert "at or below buy threshold" in result.reason
    assert result.indicators == {"close": 97.0, "ma_20": 100.0, "disparity_pct": 97.0}


def test_disparity_strategy_returns_sell_signal_above_sell_threshold():
    strategy = DisparityStrategy()

    result = strategy.evaluate({"close": 103.0, "ma_20": 100.0})

    assert result.signal is Signal.SELL
    assert "at or above sell threshold" in result.reason
    assert result.indicators == {"close": 103.0, "ma_20": 100.0, "disparity_pct": 103.0}


def test_disparity_strategy_returns_hold_signal_inside_band():
    strategy = DisparityStrategy()

    result = strategy.evaluate({"close": 100.0, "ma_20": 100.0})

    assert result.signal is Signal.HOLD
    assert "inside the disparity band" in result.reason
    assert result.indicators == {"close": 100.0, "ma_20": 100.0, "disparity_pct": 100.0}


def test_disparity_strategy_returns_hold_with_missing_indicator_reason_and_empty_indicators():
    strategy = DisparityStrategy()

    result = strategy.evaluate({"close": 100.0})

    assert result.signal is Signal.HOLD
    assert result.reason == "Missing indicators: ma_20"
    assert result.indicators == {}


def test_disparity_strategy_returns_hold_for_zero_baseline():
    strategy = DisparityStrategy()

    result = strategy.evaluate({"close": 100.0, "ma_20": 0.0})

    assert result.signal is Signal.HOLD
    assert result.reason == "Invalid baseline: ma_20 is zero."
    assert result.indicators == {}


def test_disparity_strategy_treats_nan_as_missing_indicator():
    strategy = DisparityStrategy()

    result = strategy.evaluate({"close": nan, "ma_20": 100.0})

    assert result.signal is Signal.HOLD
    assert result.reason == "Missing indicators: close"
    assert result.indicators == {}
