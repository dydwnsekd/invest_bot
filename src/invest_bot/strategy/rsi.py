from __future__ import annotations

from .base import Signal, Strategy, StrategyResult, missing_indicators_result, to_float


class RSIStrategy(Strategy):
    """Generate buy/sell/hold from RSI threshold levels."""

    name = "rsi"

    def __init__(self, rsi_column: str = "rsi_14", buy_threshold: float = 30.0, sell_threshold: float = 70.0) -> None:
        self.rsi_column = rsi_column
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def evaluate(self, market_snapshot: dict[str, float]) -> StrategyResult:
        rsi_value = to_float(market_snapshot.get(self.rsi_column))
        if rsi_value is None:
            return missing_indicators_result(self.rsi_column)

        indicators = {self.rsi_column: rsi_value}
        if rsi_value <= self.buy_threshold:
            return StrategyResult(
                Signal.BUY,
                f"{self.rsi_column} is {rsi_value:.2f}, at or below buy threshold {self.buy_threshold:.2f}.",
                indicators,
            )
        if rsi_value >= self.sell_threshold:
            return StrategyResult(
                Signal.SELL,
                f"{self.rsi_column} is {rsi_value:.2f}, at or above sell threshold {self.sell_threshold:.2f}.",
                indicators,
            )
        return StrategyResult(
            Signal.HOLD,
            f"{self.rsi_column} is {rsi_value:.2f}, between buy threshold {self.buy_threshold:.2f} and sell threshold {self.sell_threshold:.2f}.",
            indicators,
        )
