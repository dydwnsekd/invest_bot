from __future__ import annotations

import pandas as pd

from .base import Signal, Strategy, StrategyResult, missing_indicators_result, to_float


class GoldenCrossStrategy(Strategy):
    """Generate buy/sell/hold from short and long moving average crossovers."""

    name = "golden-cross"

    def __init__(self, short_column: str = "ma_5", long_column: str = "ma_20") -> None:
        self.short_column = short_column
        self.long_column = long_column

    def evaluate(self, market_snapshot: dict[str, float]) -> StrategyResult:
        prev_short = market_snapshot.get(f"prev_{self.short_column}")
        prev_long = market_snapshot.get(f"prev_{self.long_column}")
        curr_short = market_snapshot.get(self.short_column)
        curr_long = market_snapshot.get(self.long_column)

        numeric_values = {
            f"prev_{self.short_column}": to_float(prev_short),
            f"prev_{self.long_column}": to_float(prev_long),
            self.short_column: to_float(curr_short),
            self.long_column: to_float(curr_long),
        }
        missing = [key for key, value in numeric_values.items() if value is None]
        if missing:
            return missing_indicators_result(*missing)

        indicators = numeric_values

        prev_short_value = indicators[f"prev_{self.short_column}"]
        prev_long_value = indicators[f"prev_{self.long_column}"]
        curr_short_value = indicators[self.short_column]
        curr_long_value = indicators[self.long_column]

        if prev_short_value < prev_long_value and curr_short_value > curr_long_value:
            return StrategyResult(
                Signal.BUY,
                f"{self.short_column} crossed above {self.long_column}.",
                indicators,
            )

        if prev_short_value > prev_long_value and curr_short_value < curr_long_value:
            return StrategyResult(
                Signal.SELL,
                f"{self.short_column} crossed below {self.long_column}.",
                indicators,
            )

        return StrategyResult(
            Signal.HOLD,
            f"{self.short_column} and {self.long_column} did not cross.",
            indicators,
        )

    def evaluate_frame(self, frame: pd.DataFrame) -> StrategyResult:
        if len(frame) < 2:
            return StrategyResult(Signal.HOLD, "At least two rows are required to detect a crossover.")

        sorted_frame = frame.sort_values("date").reset_index(drop=True) if "date" in frame.columns else frame.reset_index(drop=True)
        latest = sorted_frame.tail(2)

        market_snapshot = {
            f"prev_{self.short_column}": to_float(latest.iloc[0].get(self.short_column)),
            f"prev_{self.long_column}": to_float(latest.iloc[0].get(self.long_column)),
            self.short_column: to_float(latest.iloc[1].get(self.short_column)),
            self.long_column: to_float(latest.iloc[1].get(self.long_column)),
        }
        return self.evaluate(market_snapshot)
