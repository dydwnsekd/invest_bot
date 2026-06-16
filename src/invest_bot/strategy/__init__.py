"""Strategy interfaces, built-in signals, and package-root strategy facade."""

from .base import Signal, Strategy, StrategyResult
from .golden_cross import GoldenCrossStrategy
from .mean_reversion import MeanReversionStrategy
from .rsi import RSIStrategy
from .trend_filter import TrendFilterStrategy

__all__ = [
    "Signal",
    "Strategy",
    "StrategyResult",
    "GoldenCrossStrategy",
    "RSIStrategy",
    "TrendFilterStrategy",
    "MeanReversionStrategy",
]
