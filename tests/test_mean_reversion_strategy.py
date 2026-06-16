from math import nan

from invest_bot.strategy import MeanReversionStrategy, Signal


def test_mean_reversion_strategy_returns_buy_signal_below_buy_ratio():
    strategy = MeanReversionStrategy()

    result = strategy.evaluate({"close": 96.0, "ma_20": 100.0})

    assert result.signal is Signal.BUY
    assert "at or below buy ratio" in result.reason
    assert result.indicators == {"close": 96.0, "ma_20": 100.0, "price_to_baseline_ratio": 0.96}


def test_mean_reversion_strategy_returns_sell_signal_above_sell_ratio():
    strategy = MeanReversionStrategy()

    result = strategy.evaluate({"close": 104.0, "ma_20": 100.0})

    assert result.signal is Signal.SELL
    assert "at or above sell ratio" in result.reason
    assert result.indicators == {"close": 104.0, "ma_20": 100.0, "price_to_baseline_ratio": 1.04}


def test_mean_reversion_strategy_returns_hold_signal_inside_band():
    strategy = MeanReversionStrategy()

    result = strategy.evaluate({"close": 100.0, "ma_20": 100.0})

    assert result.signal is Signal.HOLD
    assert "inside the mean-reversion band" in result.reason
    assert result.indicators == {"close": 100.0, "ma_20": 100.0, "price_to_baseline_ratio": 1.0}


def test_mean_reversion_strategy_returns_hold_with_missing_indicator_reason_and_empty_indicators():
    strategy = MeanReversionStrategy()

    result = strategy.evaluate({"close": 100.0})

    assert result.signal is Signal.HOLD
    assert result.reason == "Missing indicators: ma_20"
    assert result.indicators == {}


def test_mean_reversion_strategy_treats_nan_as_missing_indicator():
    strategy = MeanReversionStrategy()

    result = strategy.evaluate({"close": nan, "ma_20": 100.0})

    assert result.signal is Signal.HOLD
    assert result.reason == "Missing indicators: close"
    assert result.indicators == {}
