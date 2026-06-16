from __future__ import annotations

from .base import Signal, Strategy, StrategyResult, missing_indicators_result, to_float


class TrendFilterStrategy(Strategy):
    """Generate buy/sell/hold from long moving average trend direction."""

    name = "trend-filter"

    def __init__(self, close_column: str = "close", baseline_column: str = "ma_60", previous_close_column: str = "prev_close") -> None:
        self.close_column = close_column
        self.baseline_column = baseline_column
        self.previous_close_column = previous_close_column

    def evaluate(self, market_snapshot: dict[str, float]) -> StrategyResult:
        close_value = to_float(market_snapshot.get(self.close_column))
        baseline_value = to_float(market_snapshot.get(self.baseline_column))
        previous_close_value = to_float(market_snapshot.get(self.previous_close_column))

        missing = [
            name
            for name, value in (
                (self.close_column, close_value),
                (self.baseline_column, baseline_value),
                (self.previous_close_column, previous_close_value),
            )
            if value is None
        ]
        if missing:
            return missing_indicators_result(*missing)

        indicators = {
            self.close_column: close_value,
            self.baseline_column: baseline_value,
            self.previous_close_column: previous_close_value,
        }
        if close_value > baseline_value and close_value > previous_close_value:
            return StrategyResult(
                Signal.BUY,
                f"{self.close_column} is {close_value:.2f}, above {self.baseline_column} {baseline_value:.2f} and above {self.previous_close_column} {previous_close_value:.2f}.",
                indicators,
            )
        if close_value < baseline_value and close_value < previous_close_value:
            return StrategyResult(
                Signal.SELL,
                f"{self.close_column} is {close_value:.2f}, below {self.baseline_column} {baseline_value:.2f} and below {self.previous_close_column} {previous_close_value:.2f}.",
                indicators,
            )
        return StrategyResult(
            Signal.HOLD,
            f"{self.close_column} is {close_value:.2f}, showing a mixed signal versus {self.baseline_column} {baseline_value:.2f} and {self.previous_close_column} {previous_close_value:.2f}.",
            indicators,
        )
