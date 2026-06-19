from math import nan

from invest_bot.strategy import MomentumStrategy, Signal


def test_momentum_strategy_returns_buy_signal_above_buy_threshold():
    strategy = MomentumStrategy()

    result = strategy.evaluate({"momentum_20": 12.0})

    assert result.signal is Signal.BUY
    assert "at or above buy threshold" in result.reason
    assert result.indicators == {"momentum_20": 12.0}


def test_momentum_strategy_returns_sell_signal_below_sell_threshold():
    strategy = MomentumStrategy()

    result = strategy.evaluate({"momentum_20": -12.0})

    assert result.signal is Signal.SELL
    assert "at or below sell threshold" in result.reason
    assert result.indicators == {"momentum_20": -12.0}


def test_momentum_strategy_returns_hold_signal_inside_band():
    strategy = MomentumStrategy()

    result = strategy.evaluate({"momentum_20": 3.0})

    assert result.signal is Signal.HOLD
    assert "between buy threshold" in result.reason
    assert result.indicators == {"momentum_20": 3.0}


def test_momentum_strategy_returns_hold_with_missing_indicator_reason_and_empty_indicators():
    strategy = MomentumStrategy()

    result = strategy.evaluate({})

    assert result.signal is Signal.HOLD
    assert result.reason == "Missing indicators: momentum_20"
    assert result.indicators == {}


def test_momentum_strategy_treats_nan_as_missing_indicator():
    strategy = MomentumStrategy()

    result = strategy.evaluate({"momentum_20": nan})

    assert result.signal is Signal.HOLD
    assert result.reason == "Missing indicators: momentum_20"
    assert result.indicators == {}
