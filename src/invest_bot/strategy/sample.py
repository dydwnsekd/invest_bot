from __future__ import annotations

from .base import Signal, Strategy, StrategyResult


class ThresholdMomentumStrategy(Strategy):
    """Tiny starter strategy for smoke tests and interface validation."""

    name = "threshold-momentum"

    def __init__(self, buy_above: float = 0.5, sell_below: float = -0.5) -> None:
        self.buy_above = buy_above
        self.sell_below = sell_below

    def evaluate(self, market_snapshot: dict[str, float]) -> StrategyResult:
        momentum = market_snapshot.get("momentum", 0.0)
        if momentum >= self.buy_above:
            return StrategyResult(Signal.BUY, "Momentum exceeded buy threshold.", {"momentum": momentum})
        if momentum <= self.sell_below:
            return StrategyResult(Signal.SELL, "Momentum fell below sell threshold.", {"momentum": momentum})
        return StrategyResult(Signal.HOLD, "Momentum is between thresholds.", {"momentum": momentum})
