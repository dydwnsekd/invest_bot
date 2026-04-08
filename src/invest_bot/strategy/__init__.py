"""Strategy interfaces and built-in signals."""

from .base import Signal, Strategy, StrategyResult
from .golden_cross import GoldenCrossStrategy

__all__ = ["Signal", "Strategy", "StrategyResult", "GoldenCrossStrategy"]
