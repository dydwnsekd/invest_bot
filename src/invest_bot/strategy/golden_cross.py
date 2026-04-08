from __future__ import annotations

import pandas as pd

from .base import Signal, Strategy, StrategyResult


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

        missing = [
            key
            for key, value in {
                f"prev_{self.short_column}": prev_short,
                f"prev_{self.long_column}": prev_long,
                self.short_column: curr_short,
                self.long_column: curr_long,
            }.items()
            if value is None
        ]
        if missing:
            return StrategyResult(Signal.HOLD, f"Missing indicators: {', '.join(missing)}")

        indicators = {
            f"prev_{self.short_column}": float(prev_short),
            f"prev_{self.long_column}": float(prev_long),
            self.short_column: float(curr_short),
            self.long_column: float(curr_long),
        }

        if prev_short < prev_long and curr_short > curr_long:
            return StrategyResult(
                Signal.BUY,
                f"{self.short_column} crossed above {self.long_column}.",
                indicators,
            )

        if prev_short > prev_long and curr_short < curr_long:
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
            f"prev_{self.short_column}": self._to_number(latest.iloc[0].get(self.short_column)),
            f"prev_{self.long_column}": self._to_number(latest.iloc[0].get(self.long_column)),
            self.short_column: self._to_number(latest.iloc[1].get(self.short_column)),
            self.long_column: self._to_number(latest.iloc[1].get(self.long_column)),
        }
        return self.evaluate(market_snapshot)

    @staticmethod
    def _to_number(value: object) -> float | None:
        if value is None or pd.isna(value):
            return None
        return float(value)
