from __future__ import annotations

from .base import Signal, Strategy, StrategyResult, missing_indicators_result, to_float


class MomentumStrategy(Strategy):
    """Generate buy/sell/hold from a precomputed momentum percentage input."""

    name = "momentum"

    def __init__(
        self,
        momentum_key: str = "momentum_20",
        buy_above: float = 10.0,
        sell_below: float = -10.0,
    ) -> None:
        self.momentum_key = momentum_key
        self.buy_above = buy_above
        self.sell_below = sell_below

    def evaluate(self, market_snapshot: dict[str, float]) -> StrategyResult:
        momentum_value = to_float(market_snapshot.get(self.momentum_key))
        if momentum_value is None:
            return missing_indicators_result(self.momentum_key)

        indicators = {self.momentum_key: momentum_value}
        if momentum_value >= self.buy_above:
            return StrategyResult(
                Signal.BUY,
                f"{self.momentum_key} is {momentum_value:.2f}, at or above buy threshold {self.buy_above:.2f}.",
                indicators,
            )
        if momentum_value <= self.sell_below:
            return StrategyResult(
                Signal.SELL,
                f"{self.momentum_key} is {momentum_value:.2f}, at or below sell threshold {self.sell_below:.2f}.",
                indicators,
            )
        return StrategyResult(
            Signal.HOLD,
            f"{self.momentum_key} is {momentum_value:.2f}, between buy threshold {self.buy_above:.2f} and sell threshold {self.sell_below:.2f}.",
            indicators,
        )
