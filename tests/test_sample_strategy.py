from invest_bot.strategy.base import Signal
from invest_bot.strategy.sample import ThresholdMomentumStrategy


def test_threshold_momentum_strategy_returns_buy_signal():
    strategy = ThresholdMomentumStrategy(buy_above=1.0, sell_below=-1.0)

    result = strategy.evaluate({"momentum": 1.2})

    assert result.signal is Signal.BUY
    assert result.indicators["momentum"] == 1.2
