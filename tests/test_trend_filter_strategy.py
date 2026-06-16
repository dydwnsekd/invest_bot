from math import nan

from invest_bot.strategy import Signal, TrendFilterStrategy


def test_trend_filter_strategy_returns_buy_signal_in_bullish_setup():
    strategy = TrendFilterStrategy()

    result = strategy.evaluate({"close": 105.0, "ma_60": 100.0, "prev_close": 101.0})

    assert result.signal is Signal.BUY
    assert "above ma_60" in result.reason
    assert result.indicators == {"close": 105.0, "ma_60": 100.0, "prev_close": 101.0}


def test_trend_filter_strategy_returns_sell_signal_in_bearish_setup():
    strategy = TrendFilterStrategy()

    result = strategy.evaluate({"close": 95.0, "ma_60": 100.0, "prev_close": 99.0})

    assert result.signal is Signal.SELL
    assert "below ma_60" in result.reason
    assert result.indicators == {"close": 95.0, "ma_60": 100.0, "prev_close": 99.0}


def test_trend_filter_strategy_returns_hold_signal_for_mixed_setup():
    strategy = TrendFilterStrategy()

    result = strategy.evaluate({"close": 101.0, "ma_60": 100.0, "prev_close": 102.0})

    assert result.signal is Signal.HOLD
    assert "mixed signal" in result.reason
    assert result.indicators == {"close": 101.0, "ma_60": 100.0, "prev_close": 102.0}


def test_trend_filter_strategy_returns_hold_with_missing_indicator_reason_and_empty_indicators():
    strategy = TrendFilterStrategy()

    result = strategy.evaluate({"close": 101.0, "ma_60": 100.0})

    assert result.signal is Signal.HOLD
    assert result.reason == "Missing indicators: prev_close"
    assert result.indicators == {}


def test_trend_filter_strategy_treats_nan_as_missing_indicator():
    strategy = TrendFilterStrategy()

    result = strategy.evaluate({"close": 101.0, "ma_60": 100.0, "prev_close": nan})

    assert result.signal is Signal.HOLD
    assert result.reason == "Missing indicators: prev_close"
    assert result.indicators == {}
