from __future__ import annotations

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
