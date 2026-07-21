from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

import pandas as pd

from invest_bot.strategy import (
    DisparityStrategy,
    GoldenCrossStrategy,
    InvestorFlowCustomStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    RSIStrategy,
    TrendFilterStrategy,
)
from invest_bot.strategy.base import StrategyResult

from .readiness import RunReadinessGate, build_run_readiness_gate
from .strategy_registry import (
    BACKTEST_STRATEGY_SPECS,
    DAILY_PRICES_INDICATORS,
    INVESTOR_DAILY,
    BacktestStrategySpec,
)

GOLDEN_CROSS_SIGNALS = "golden_cross_signals"


@dataclass(frozen=True)
class BacktestAdapterOutput:
    strategy_id: str
    strategy_name: str
    signal_rows: pd.DataFrame


class BacktestDataReadinessError(ValueError):
    """Raised when a requested backtest strategy cannot be assembled safely."""

    def __init__(self, gate: RunReadinessGate) -> None:
        self.gate = gate
        super().__init__("; ".join(gate.blocking_reasons) or "backtest data is not ready")


AdapterFn = Callable[[Mapping[str, pd.DataFrame | None], BacktestStrategySpec], pd.DataFrame]


class BacktestStrategyAdapterRegistry:
    """Build per-strategy normalized signal rows from source datasets."""

    def __init__(self) -> None:
        self._adapters: dict[str, AdapterFn] = {
            "golden-cross": _adapt_golden_cross,
            "rsi": _adapt_rsi,
            "trend-filter": _adapt_trend_filter,
            "mean-reversion": _adapt_mean_reversion,
            "disparity": _adapt_disparity,
            "momentum": _adapt_momentum,
            "investor-flow-custom": _adapt_investor_flow,
        }

    def build_signal_rows(
        self,
        strategy_id: str,
        datasets: Mapping[str, pd.DataFrame | None],
        *,
        registry: Mapping[str, BacktestStrategySpec] = BACKTEST_STRATEGY_SPECS,
    ) -> BacktestAdapterOutput:
        spec = registry[strategy_id]
        if strategy_id != "golden-cross" or DAILY_PRICES_INDICATORS in datasets:
            gate = build_run_readiness_gate([strategy_id], datasets, registry=registry)
            if not gate.can_run:
                raise BacktestDataReadinessError(gate)

        signal_rows = self._adapters[strategy_id](datasets, spec)
        return BacktestAdapterOutput(
            strategy_id=strategy_id,
            strategy_name=spec.strategy_name,
            signal_rows=signal_rows,
        )



def build_strategy_signal_rows(
    strategy_id: str,
    datasets: Mapping[str, pd.DataFrame | None],
    *,
    registry: Mapping[str, BacktestStrategySpec] = BACKTEST_STRATEGY_SPECS,
) -> pd.DataFrame:
    """Build normalized signal rows for one registered strategy."""

    return DEFAULT_BACKTEST_ADAPTER_REGISTRY.build_signal_rows(strategy_id, datasets, registry=registry).signal_rows


def _adapt_golden_cross(datasets: Mapping[str, pd.DataFrame | None], spec: BacktestStrategySpec) -> pd.DataFrame:
    signal_frame = datasets.get(GOLDEN_CROSS_SIGNALS)
    if signal_frame is not None and {"date", "close", "signal"}.issubset(signal_frame.columns):
        return _normalize_existing_signal_frame(signal_frame, spec)

    frame = _prepare_price_frame(datasets.get(DAILY_PRICES_INDICATORS))
    strategy = GoldenCrossStrategy()
    result = frame.copy()
    result["signal"] = "hold"
    result["signal_reason"] = "At least two rows are required to detect a crossover."
    result["strategy_id"] = spec.strategy_id
    result["strategy_name"] = spec.strategy_name
    result["prev_ma_5"] = result["ma_5"].shift(1)
    result["prev_ma_20"] = result["ma_20"].shift(1)

    for index in range(1, len(result)):
        signal_result = strategy.evaluate_frame(result.iloc[index - 1 : index + 1])
        _apply_strategy_result(result, index, signal_result)

    return result


def _adapt_rsi(datasets: Mapping[str, pd.DataFrame | None], spec: BacktestStrategySpec) -> pd.DataFrame:
    return _apply_row_strategy(_prepare_price_frame(datasets[DAILY_PRICES_INDICATORS]), spec, RSIStrategy())


def _adapt_trend_filter(datasets: Mapping[str, pd.DataFrame | None], spec: BacktestStrategySpec) -> pd.DataFrame:
    frame = _prepare_price_frame(datasets[DAILY_PRICES_INDICATORS])
    frame["prev_close"] = frame["close"].shift(1)
    return _apply_row_strategy(frame, spec, TrendFilterStrategy())


def _adapt_mean_reversion(datasets: Mapping[str, pd.DataFrame | None], spec: BacktestStrategySpec) -> pd.DataFrame:
    return _apply_row_strategy(_prepare_price_frame(datasets[DAILY_PRICES_INDICATORS]), spec, MeanReversionStrategy())


def _adapt_disparity(datasets: Mapping[str, pd.DataFrame | None], spec: BacktestStrategySpec) -> pd.DataFrame:
    return _apply_row_strategy(_prepare_price_frame(datasets[DAILY_PRICES_INDICATORS]), spec, DisparityStrategy())


def _adapt_momentum(datasets: Mapping[str, pd.DataFrame | None], spec: BacktestStrategySpec) -> pd.DataFrame:
    return _apply_row_strategy(_prepare_price_frame(datasets[DAILY_PRICES_INDICATORS]), spec, MomentumStrategy())


def _adapt_investor_flow(datasets: Mapping[str, pd.DataFrame | None], spec: BacktestStrategySpec) -> pd.DataFrame:
    frame = _prepare_price_frame(datasets[DAILY_PRICES_INDICATORS])
    investor_frame = _prepare_investor_frame(datasets[INVESTOR_DAILY])
    merged = frame.merge(investor_frame, on="date", how="left", validate="one_to_one")
    return _apply_row_strategy(merged, spec, InvestorFlowCustomStrategy())


def _apply_row_strategy(frame: pd.DataFrame, spec: BacktestStrategySpec, strategy: RSIStrategy | TrendFilterStrategy | MeanReversionStrategy | DisparityStrategy | MomentumStrategy | InvestorFlowCustomStrategy) -> pd.DataFrame:
    result = frame.copy()
    result["strategy_id"] = spec.strategy_id
    result["strategy_name"] = spec.strategy_name
    result["signal"] = "hold"
    result["signal_reason"] = "No strategy evaluation was recorded."

    for index, row in result.iterrows():
        signal_result = strategy.evaluate(row.to_dict())
        _apply_strategy_result(result, index, signal_result)
        for key, value in signal_result.indicators.items():
            result.at[index, key] = value

    return result


def _apply_strategy_result(frame: pd.DataFrame, index: int, signal_result: StrategyResult) -> None:
    frame.at[index, "signal"] = signal_result.signal.value
    frame.at[index, "signal_reason"] = signal_result.reason
    for key, value in signal_result.indicators.items():
        frame.at[index, key] = value


def _normalize_existing_signal_frame(frame: pd.DataFrame, spec: BacktestStrategySpec) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    result = result.sort_values("date").reset_index(drop=True)
    result["strategy_id"] = spec.strategy_id
    result["strategy_name"] = spec.strategy_name
    result["signal"] = result["signal"].astype(str).str.lower()
    if "signal_reason" not in result.columns:
        result["signal_reason"] = ""
    result["signal_reason"] = result["signal_reason"].fillna("").astype(str)
    return result


def _prepare_price_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None:
        return pd.DataFrame(columns=["date", "close"])
    result = frame.copy()
    if "date" in result.columns:
        result["date"] = pd.to_datetime(result["date"], errors="coerce")
        result = result.sort_values("date").reset_index(drop=True)
    return result


def _prepare_investor_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None:
        return pd.DataFrame(columns=["date", "foreign_net_qty", "institutional_net_qty"])
    result = frame.copy()
    date_column = "date" if "date" in result.columns else "trade_date"
    result["date"] = pd.to_datetime(result[date_column], errors="coerce")
    if date_column != "date" and date_column in result.columns:
        result = result.drop(columns=[date_column])
    return result.sort_values("date").reset_index(drop=True)


DEFAULT_BACKTEST_ADAPTER_REGISTRY = BacktestStrategyAdapterRegistry()
