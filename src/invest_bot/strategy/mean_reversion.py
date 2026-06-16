from __future__ import annotations

from .base import Signal, Strategy, StrategyResult, missing_indicators_result, to_float


class MeanReversionStrategy(Strategy):
    """Generate buy/sell/hold from deviation around a moving-average baseline."""

    name = "mean-reversion"

    def __init__(
        self,
        close_column: str = "close",
        baseline_column: str = "ma_20",
        buy_ratio: float = 0.97,
        sell_ratio: float = 1.03,
    ) -> None:
        self.close_column = close_column
        self.baseline_column = baseline_column
        self.buy_ratio = buy_ratio
        self.sell_ratio = sell_ratio

    def evaluate(self, market_snapshot: dict[str, float]) -> StrategyResult:
        close_value = to_float(market_snapshot.get(self.close_column))
        baseline_value = to_float(market_snapshot.get(self.baseline_column))

        missing = [
            name
            for name, value in (
                (self.close_column, close_value),
                (self.baseline_column, baseline_value),
            )
            if value is None
        ]
        if missing:
            return missing_indicators_result(*missing)

        ratio = close_value / baseline_value if baseline_value else None
        if ratio is None:
            return missing_indicators_result(self.baseline_column)

        indicators = {
            self.close_column: close_value,
            self.baseline_column: baseline_value,
            "price_to_baseline_ratio": ratio,
        }
        if ratio <= self.buy_ratio:
            return StrategyResult(
                Signal.BUY,
                f"{self.close_column} is {close_value:.2f}, at {ratio:.4f} of {self.baseline_column} {baseline_value:.2f}, at or below buy ratio {self.buy_ratio:.4f}.",
                indicators,
            )
        if ratio >= self.sell_ratio:
            return StrategyResult(
                Signal.SELL,
                f"{self.close_column} is {close_value:.2f}, at {ratio:.4f} of {self.baseline_column} {baseline_value:.2f}, at or above sell ratio {self.sell_ratio:.4f}.",
                indicators,
            )
        return StrategyResult(
            Signal.HOLD,
            f"{self.close_column} is {close_value:.2f}, at {ratio:.4f} of {self.baseline_column} {baseline_value:.2f}, inside the mean-reversion band.",
            indicators,
        )
