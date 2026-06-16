from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum


class Signal(StrEnum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass(slots=True)
class StrategyResult:
    signal: Signal
    reason: str
    indicators: dict[str, float] = field(default_factory=dict)


class Strategy(ABC):
    name: str = "base-strategy"

    @abstractmethod
    def evaluate(self, market_snapshot: dict[str, float]) -> StrategyResult:
        """Return a signal from normalized market input."""


def missing_indicators_result(*names: str) -> StrategyResult:
    return StrategyResult(Signal.HOLD, f"Missing indicators: {', '.join(names)}")


def to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number
