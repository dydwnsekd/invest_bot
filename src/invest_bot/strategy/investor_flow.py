from __future__ import annotations

from .base import Signal, Strategy, StrategyResult, missing_indicators_result, to_float


class InvestorFlowCustomStrategy(Strategy):
    """Generate buy/sell/hold from combined investor flow and price filter inputs."""

    name = "investor-flow-custom"

    def __init__(
        self,
        foreign_column: str = "foreign_net_qty",
        institutional_column: str = "institutional_net_qty",
        close_column: str = "close",
        baseline_column: str = "ma_20",
    ) -> None:
        self.foreign_column = foreign_column
        self.institutional_column = institutional_column
        self.close_column = close_column
        self.baseline_column = baseline_column

    def evaluate(self, market_snapshot: dict[str, float]) -> StrategyResult:
        foreign_value = to_float(market_snapshot.get(self.foreign_column))
        institutional_value = to_float(market_snapshot.get(self.institutional_column))
        close_value = to_float(market_snapshot.get(self.close_column))
        baseline_value = to_float(market_snapshot.get(self.baseline_column))

        missing = [
            name
            for name, value in (
                (self.foreign_column, foreign_value),
                (self.institutional_column, institutional_value),
                (self.close_column, close_value),
                (self.baseline_column, baseline_value),
            )
            if value is None
        ]
        if missing:
            return missing_indicators_result(*missing)
        if baseline_value == 0:
            return StrategyResult(Signal.HOLD, f"Invalid baseline: {self.baseline_column} is zero.")

        indicators = {
            self.foreign_column: foreign_value,
            self.institutional_column: institutional_value,
            self.close_column: close_value,
            self.baseline_column: baseline_value,
        }
        if foreign_value > 0 and institutional_value > 0 and close_value > baseline_value:
            return StrategyResult(
                Signal.BUY,
                f"{self.foreign_column} and {self.institutional_column} are positive while {self.close_column} is above {self.baseline_column}.",
                indicators,
            )
        if foreign_value < 0 and institutional_value < 0 and close_value < baseline_value:
            return StrategyResult(
                Signal.SELL,
                f"{self.foreign_column} and {self.institutional_column} are negative while {self.close_column} is below {self.baseline_column}.",
                indicators,
            )
        return StrategyResult(
            Signal.HOLD,
            f"Investor flow and price filter produce a mixed signal for {self.close_column} versus {self.baseline_column}.",
            indicators,
        )
