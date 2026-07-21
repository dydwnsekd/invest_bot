"""Backtest scaffolding for invest_bot."""

from .adapters import (
    DEFAULT_BACKTEST_ADAPTER_REGISTRY,
    GOLDEN_CROSS_SIGNALS,
    BacktestAdapterOutput,
    BacktestDataReadinessError,
    BacktestStrategyAdapterRegistry,
    build_strategy_signal_rows,
)
from .readiness import (
    BacktestReadinessResult,
    RunReadinessGate,
    StrategyReadiness,
    build_run_readiness_gate,
    check_backtest_readiness,
)
from .runner import BacktestResult, DEFAULT_BACKTEST_RUNNER, NormalizedSignalBacktestRunner
from .strategy_registry import (
    BACKTEST_STRATEGY_IDS,
    BACKTEST_STRATEGY_SPECS,
    BacktestStrategySpec,
    DatasetRequirement,
    get_backtest_strategy_spec,
    list_backtest_strategy_specs,
)

__all__ = [
    "BACKTEST_STRATEGY_IDS",
    "BACKTEST_STRATEGY_SPECS",
    "BacktestAdapterOutput",
    "BacktestDataReadinessError",
    "BacktestReadinessResult",
    "BacktestResult",
    "BacktestStrategyAdapterRegistry",
    "BacktestStrategySpec",
    "DEFAULT_BACKTEST_ADAPTER_REGISTRY",
    "DEFAULT_BACKTEST_RUNNER",
    "DatasetRequirement",
    "GOLDEN_CROSS_SIGNALS",
    "NormalizedSignalBacktestRunner",
    "RunReadinessGate",
    "StrategyReadiness",
    "build_run_readiness_gate",
    "build_strategy_signal_rows",
    "check_backtest_readiness",
    "get_backtest_strategy_spec",
    "list_backtest_strategy_specs",
]
