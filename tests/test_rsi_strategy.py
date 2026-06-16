from math import nan

from invest_bot.strategy import RSIStrategy, Signal


def test_rsi_strategy_returns_buy_signal_below_buy_threshold():
    strategy = RSIStrategy()

    result = strategy.evaluate({"rsi_14": 25.0})

    assert result.signal is Signal.BUY
    assert "at or below buy threshold" in result.reason
    assert result.indicators == {"rsi_14": 25.0}


def test_rsi_strategy_returns_sell_signal_above_sell_threshold():
    strategy = RSIStrategy()

    result = strategy.evaluate({"rsi_14": 75.0})

    assert result.signal is Signal.SELL
    assert "at or above sell threshold" in result.reason
    assert result.indicators == {"rsi_14": 75.0}


def test_rsi_strategy_returns_hold_signal_inside_neutral_band():
    strategy = RSIStrategy()

    result = strategy.evaluate({"rsi_14": 55.0})

    assert result.signal is Signal.HOLD
    assert "between buy threshold" in result.reason
    assert result.indicators == {"rsi_14": 55.0}


def test_rsi_strategy_returns_hold_with_missing_indicator_reason_and_empty_indicators():
    strategy = RSIStrategy()

    result = strategy.evaluate({})

    assert result.signal is Signal.HOLD
    assert result.reason == "Missing indicators: rsi_14"
    assert result.indicators == {}


def test_rsi_strategy_treats_nan_as_missing_indicator():
    strategy = RSIStrategy()

    result = strategy.evaluate({"rsi_14": nan})

    assert result.signal is Signal.HOLD
    assert result.reason == "Missing indicators: rsi_14"
    assert result.indicators == {}
