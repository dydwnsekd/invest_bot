"""Strategy interfaces, built-in signals, and package-root strategy facade."""

from .base import Signal, Strategy, StrategyResult
from .disparity import DisparityStrategy
from .golden_cross import GoldenCrossStrategy
from .investor_flow import InvestorFlowCustomStrategy
from .mean_reversion import MeanReversionStrategy
from .momentum import MomentumStrategy
from .rsi import RSIStrategy
from .trend_filter import TrendFilterStrategy

__all__ = [
    "Signal",
    "Strategy",
    "StrategyResult",
    "GoldenCrossStrategy",
    "DisparityStrategy",
    "InvestorFlowCustomStrategy",
    "RSIStrategy",
    "TrendFilterStrategy",
    "MeanReversionStrategy",
    "MomentumStrategy",
]
