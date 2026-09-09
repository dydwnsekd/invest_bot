"""Backtest scaffolding for invest_bot."""

from .adapters import (
    DEFAULT_BACKTEST_ADAPTER_REGISTRY,
    GOLDEN_CROSS_SIGNALS,
    BacktestAdapterOutput,
    BacktestDataReadinessError,
    BacktestStrategyAdapterRegistry,
    build_strategy_signal_rows,
)
from .combination import (
    COMBINATION_MODE_AND,
    COMBINATION_MODE_LABELS,
    COMBINATION_MODE_OR,
    COMBINATION_MODE_WEIGHTED,
    BacktestCombinationSettings,
    combine_strategy_signal_rows,
    resolve_backtest_combination_settings,
)
from .readiness import (
    BacktestReadinessResult,
    RunReadinessGate,
    StrategyReadiness,
    build_run_readiness_gate,
    check_backtest_readiness,
)
from .parameters import (
    BacktestParameterDefinition,
    default_backtest_parameters,
    format_backtest_parameters,
    is_default_backtest_parameters,
    list_backtest_parameter_definitions,
    resolve_backtest_parameters,
)
from .portfolio import (
    PORTFOLIO_DATE_POLICY,
    PORTFOLIO_REBALANCING_METHOD,
    PORTFOLIO_WEIGHTING_METHOD,
    PortfolioAggregationResult,
    build_equal_weight_portfolios,
)
from .runner import (
    DEFAULT_BACKTEST_RUNNER,
    DEFAULT_MARK_TO_MARKET_INITIAL_EQUITY,
    BacktestResult,
    NormalizedSignalBacktestRunner,
    build_daily_mark_to_market_equity_curve,
)
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
    "COMBINATION_MODE_AND",
    "COMBINATION_MODE_LABELS",
    "COMBINATION_MODE_OR",
    "COMBINATION_MODE_WEIGHTED",
    "BacktestAdapterOutput",
    "BacktestCombinationSettings",
    "BacktestDataReadinessError",
    "BacktestParameterDefinition",
    "BacktestReadinessResult",
    "BacktestResult",
    "BacktestStrategyAdapterRegistry",
    "BacktestStrategySpec",
    "DEFAULT_BACKTEST_ADAPTER_REGISTRY",
    "DEFAULT_BACKTEST_RUNNER",
    "DEFAULT_MARK_TO_MARKET_INITIAL_EQUITY",
    "DatasetRequirement",
    "GOLDEN_CROSS_SIGNALS",
    "NormalizedSignalBacktestRunner",
    "PORTFOLIO_DATE_POLICY",
    "PORTFOLIO_REBALANCING_METHOD",
    "PORTFOLIO_WEIGHTING_METHOD",
    "PortfolioAggregationResult",
    "RunReadinessGate",
    "StrategyReadiness",
    "build_run_readiness_gate",
    "build_daily_mark_to_market_equity_curve",
    "build_equal_weight_portfolios",
    "build_strategy_signal_rows",
    "check_backtest_readiness",
    "default_backtest_parameters",
    "format_backtest_parameters",
    "get_backtest_strategy_spec",
    "is_default_backtest_parameters",
    "list_backtest_parameter_definitions",
    "list_backtest_strategy_specs",
    "combine_strategy_signal_rows",
    "resolve_backtest_combination_settings",
    "resolve_backtest_parameters",
]
