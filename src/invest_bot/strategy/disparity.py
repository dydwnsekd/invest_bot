from __future__ import annotations

from .base import Signal, Strategy, StrategyResult, missing_indicators_result, to_float


class DisparityStrategy(Strategy):
    """Generate buy/sell/hold from percentage distance versus a moving-average baseline."""

    name = "disparity"

    def __init__(
        self,
        close_column: str = "close",
        ma_key: str = "ma_20",
        buy_below: float = 97.0,
        sell_above: float = 103.0,
    ) -> None:
        self.close_column = close_column
        self.ma_key = ma_key
        self.buy_below = buy_below
        self.sell_above = sell_above

    def evaluate(self, market_snapshot: dict[str, float]) -> StrategyResult:
        close_value = to_float(market_snapshot.get(self.close_column))
        baseline_value = to_float(market_snapshot.get(self.ma_key))

        missing = [
            name
            for name, value in (
                (self.close_column, close_value),
                (self.ma_key, baseline_value),
            )
            if value is None
        ]
        if missing:
            return missing_indicators_result(*missing)
        if baseline_value == 0:
            return StrategyResult(Signal.HOLD, f"Invalid baseline: {self.ma_key} is zero.")

        disparity_pct = (close_value / baseline_value) * 100
        indicators = {
            self.close_column: close_value,
            self.ma_key: baseline_value,
            "disparity_pct": disparity_pct,
        }
        if disparity_pct <= self.buy_below:
            return StrategyResult(
                Signal.BUY,
                f"disparity_pct is {disparity_pct:.2f}, at or below buy threshold {self.buy_below:.2f}.",
                indicators,
            )
        if disparity_pct >= self.sell_above:
            return StrategyResult(
                Signal.SELL,
                f"disparity_pct is {disparity_pct:.2f}, at or above sell threshold {self.sell_above:.2f}.",
                indicators,
            )
        return StrategyResult(
            Signal.HOLD,
            f"disparity_pct is {disparity_pct:.2f}, inside the disparity band.",
            indicators,
        )
