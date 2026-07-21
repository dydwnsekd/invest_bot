"""Backtest-specific strategy capability registry.

This module intentionally describes data contracts only.  It does not access the
DB, assemble adapters, or run a backtest.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


DAILY_PRICES_INDICATORS = "daily_prices_indicators"
INVESTOR_DAILY = "investor_daily"


@dataclass(frozen=True)
class DatasetRequirement:
    """Columns required from one logical input dataset."""

    dataset_id: str
    columns: tuple[str, ...]
    alternative_date_columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class BacktestStrategySpec:
    """Backtest-facing data contract for one supported strategy."""

    strategy_id: str
    strategy_name: str
    required_datasets: tuple[str, ...]
    required_columns: Mapping[str, tuple[str, ...]]
    derived_fields: tuple[str, ...] = ()
    provenance_needs: tuple[str, ...] = ()
    date_column_aliases: Mapping[str, tuple[str, ...]] = MappingProxyType({})

    def requirement_for(self, dataset_id: str) -> DatasetRequirement:
        return DatasetRequirement(
            dataset_id=dataset_id,
            columns=self.required_columns.get(dataset_id, ()),
            alternative_date_columns=self.date_column_aliases.get(dataset_id, ()),
        )


PRICE_PROVENANCE = (
    "indicator_source_dataset",
    "indicator_source_filename",
    "price_source_dataset",
    "price_source_filename",
)
SIGNAL_PROVENANCE = ("signal_source_dataset", "signal_source_filename")
INVESTOR_PROVENANCE = ("investor_source_dataset", "investor_source_filename")


_STRATEGY_SPECS: dict[str, BacktestStrategySpec] = {
    "golden-cross": BacktestStrategySpec(
        strategy_id="golden-cross",
        strategy_name="Golden Cross",
        required_datasets=(DAILY_PRICES_INDICATORS,),
        required_columns={DAILY_PRICES_INDICATORS: ("date", "close", "ma_5", "ma_20")},
        derived_fields=("prev_ma_5", "prev_ma_20"),
        provenance_needs=PRICE_PROVENANCE + SIGNAL_PROVENANCE,
    ),
    "rsi": BacktestStrategySpec(
        strategy_id="rsi",
        strategy_name="RSI",
        required_datasets=(DAILY_PRICES_INDICATORS,),
        required_columns={DAILY_PRICES_INDICATORS: ("date", "close", "rsi_14")},
        provenance_needs=PRICE_PROVENANCE,
    ),
    "trend-filter": BacktestStrategySpec(
        strategy_id="trend-filter",
        strategy_name="Trend Filter",
        required_datasets=(DAILY_PRICES_INDICATORS,),
        required_columns={DAILY_PRICES_INDICATORS: ("date", "close", "ma_60")},
        derived_fields=("prev_close",),
        provenance_needs=PRICE_PROVENANCE,
    ),
    "mean-reversion": BacktestStrategySpec(
        strategy_id="mean-reversion",
        strategy_name="Mean Reversion",
        required_datasets=(DAILY_PRICES_INDICATORS,),
        required_columns={DAILY_PRICES_INDICATORS: ("date", "close", "ma_20")},
        derived_fields=("price_to_baseline_ratio",),
        provenance_needs=PRICE_PROVENANCE,
    ),
    "disparity": BacktestStrategySpec(
        strategy_id="disparity",
        strategy_name="Disparity",
        required_datasets=(DAILY_PRICES_INDICATORS,),
        required_columns={DAILY_PRICES_INDICATORS: ("date", "close", "ma_20")},
        derived_fields=("disparity_pct",),
        provenance_needs=PRICE_PROVENANCE,
    ),
    "momentum": BacktestStrategySpec(
        strategy_id="momentum",
        strategy_name="Momentum",
        required_datasets=(DAILY_PRICES_INDICATORS,),
        required_columns={DAILY_PRICES_INDICATORS: ("date", "close", "momentum_20")},
        provenance_needs=PRICE_PROVENANCE,
    ),
    "investor-flow-custom": BacktestStrategySpec(
        strategy_id="investor-flow-custom",
        strategy_name="Investor Flow Custom",
        required_datasets=(DAILY_PRICES_INDICATORS, INVESTOR_DAILY),
        required_columns={
            DAILY_PRICES_INDICATORS: ("date", "close", "ma_20"),
            INVESTOR_DAILY: ("foreign_net_qty", "institutional_net_qty"),
        },
        derived_fields=("aligned_investor_flow_by_date",),
        provenance_needs=PRICE_PROVENANCE + INVESTOR_PROVENANCE,
        date_column_aliases={INVESTOR_DAILY: ("date", "trade_date")},
    ),
}

BACKTEST_STRATEGY_SPECS: Mapping[str, BacktestStrategySpec] = MappingProxyType(_STRATEGY_SPECS)
BACKTEST_STRATEGY_IDS: tuple[str, ...] = tuple(_STRATEGY_SPECS)


def get_backtest_strategy_spec(strategy_id: str) -> BacktestStrategySpec:
    """Return the registered spec for ``strategy_id`` or raise ``KeyError``."""

    return BACKTEST_STRATEGY_SPECS[strategy_id]


def list_backtest_strategy_specs() -> tuple[BacktestStrategySpec, ...]:
    """Return all backtest specs in stable UI/runner order."""

    return tuple(BACKTEST_STRATEGY_SPECS[strategy_id] for strategy_id in BACKTEST_STRATEGY_IDS)
