"""Pure pandas readiness checks for backtest strategy selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import pandas as pd

from .strategy_registry import (
    BACKTEST_STRATEGY_SPECS,
    DAILY_PRICES_INDICATORS,
    INVESTOR_DAILY,
    BacktestStrategySpec,
)


@dataclass(frozen=True)
class StrategyReadiness:
    strategy_id: str
    ready: bool
    blocking_reasons: tuple[str, ...] = ()
    missing_datasets: tuple[str, ...] = ()
    missing_columns: Mapping[str, tuple[str, ...]] | None = None


@dataclass(frozen=True)
class BacktestReadinessResult:
    selected_strategy_ids: tuple[str, ...]
    strategy_results: tuple[StrategyReadiness, ...]

    @property
    def ready_to_run(self) -> bool:
        return all(result.ready for result in self.strategy_results)

    @property
    def unready_strategy_ids(self) -> tuple[str, ...]:
        return tuple(result.strategy_id for result in self.strategy_results if not result.ready)

    @property
    def blocking_reasons(self) -> tuple[str, ...]:
        reasons: list[str] = []
        for result in self.strategy_results:
            reasons.extend(f"{result.strategy_id}: {reason}" for reason in result.blocking_reasons)
        return tuple(reasons)


@dataclass(frozen=True)
class RunReadinessGate:
    """Helper result that downstream runners can use to block instead of skip."""

    can_run: bool
    blocking_reasons: tuple[str, ...]
    readiness: BacktestReadinessResult


DatasetFrames = Mapping[str, pd.DataFrame | None]


def check_backtest_readiness(
    selected_strategy_ids: Sequence[str],
    datasets: DatasetFrames,
    *,
    registry: Mapping[str, BacktestStrategySpec] = BACKTEST_STRATEGY_SPECS,
) -> BacktestReadinessResult:
    """Check selected strategy data readiness against in-memory DataFrames.

    The function is intentionally DB-free and side-effect-free. Unknown strategy
    IDs and unready selected strategies are returned as blocking reasons; callers
    must not silently drop them.
    """

    selected = tuple(dict.fromkeys(selected_strategy_ids))
    strategy_results = tuple(_check_strategy(strategy_id, datasets, registry) for strategy_id in selected)
    return BacktestReadinessResult(selected_strategy_ids=selected, strategy_results=strategy_results)


def build_run_readiness_gate(
    selected_strategy_ids: Sequence[str],
    datasets: DatasetFrames,
    *,
    registry: Mapping[str, BacktestStrategySpec] = BACKTEST_STRATEGY_SPECS,
) -> RunReadinessGate:
    """Return a runner-facing gate that blocks when any selected strategy is unready."""

    readiness = check_backtest_readiness(selected_strategy_ids, datasets, registry=registry)
    return RunReadinessGate(
        can_run=readiness.ready_to_run,
        blocking_reasons=readiness.blocking_reasons,
        readiness=readiness,
    )


def _check_strategy(
    strategy_id: str,
    datasets: DatasetFrames,
    registry: Mapping[str, BacktestStrategySpec],
) -> StrategyReadiness:
    spec = registry.get(strategy_id)
    if spec is None:
        return StrategyReadiness(
            strategy_id=strategy_id,
            ready=False,
            blocking_reasons=("unknown strategy id is not registered for backtests",),
        )

    missing_datasets: list[str] = []
    missing_columns: dict[str, tuple[str, ...]] = {}
    reasons: list[str] = []

    for dataset_id in spec.required_datasets:
        frame = datasets.get(dataset_id)
        if frame is None:
            missing_datasets.append(dataset_id)
            reasons.append(f"missing required dataset {dataset_id}")
            continue
        if frame.empty:
            reasons.append(f"required dataset {dataset_id} is empty")

        required_columns = list(spec.required_columns.get(dataset_id, ()))
        date_aliases = spec.date_column_aliases.get(dataset_id, ())
        missing = [column for column in required_columns if column not in frame.columns]
        if date_aliases and not any(column in frame.columns for column in date_aliases):
            missing.append("date or trade_date")
        if missing:
            missing_columns[dataset_id] = tuple(missing)
            reasons.append(f"missing columns in {dataset_id}: {', '.join(missing)}")

    if strategy_id == "investor-flow-custom" and not reasons:
        alignment_reason = _investor_flow_alignment_reason(
            datasets[DAILY_PRICES_INDICATORS],
            datasets[INVESTOR_DAILY],
        )
        if alignment_reason:
            reasons.append(alignment_reason)

    return StrategyReadiness(
        strategy_id=strategy_id,
        ready=not reasons,
        blocking_reasons=tuple(reasons),
        missing_datasets=tuple(missing_datasets),
        missing_columns=missing_columns or None,
    )


def _investor_flow_alignment_reason(
    price_frame: pd.DataFrame | None,
    investor_frame: pd.DataFrame | None,
) -> str | None:
    if price_frame is None or investor_frame is None:
        return "investor-flow requires both daily_prices_indicators and investor_daily"

    price_dates = _normalized_dates(price_frame, "date")
    investor_date_column = "date" if "date" in investor_frame.columns else "trade_date"
    investor_dates = _normalized_dates(investor_frame, investor_date_column)

    if price_dates.empty:
        return "daily_prices_indicators has no parseable date values for investor-flow alignment"
    if investor_dates.empty:
        return "investor_daily has no parseable date/trade_date values for investor-flow alignment"

    price_unique = set(price_dates)
    investor_unique = set(investor_dates)
    missing_investor_dates = sorted(price_unique - investor_unique)
    if missing_investor_dates:
        sample = ", ".join(date.isoformat() for date in missing_investor_dates[:3])
        suffix = "" if len(missing_investor_dates) <= 3 else f" (+{len(missing_investor_dates) - 3} more)"
        return (
            "investor_daily is not aligned to daily_prices_indicators dates; "
            f"missing investor flow for {sample}{suffix}"
        )

    return None


def _normalized_dates(frame: pd.DataFrame, column: str) -> pd.Series:
    parsed = pd.to_datetime(frame[column], errors="coerce")
    return parsed.dropna().dt.date.drop_duplicates()
