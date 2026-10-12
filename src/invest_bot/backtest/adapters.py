from __future__ import annotations

from dataclasses import dataclass
from datetime import date
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

from .dates import local_trading_dates, require_unique_trading_dates
from .readiness import RunReadinessGate, build_run_readiness_gate
from .parameters import resolve_backtest_parameters
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


AdapterFn = Callable[[Mapping[str, pd.DataFrame | None], BacktestStrategySpec, Mapping[str, float]], pd.DataFrame]


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
        parameters: Mapping[str, object] | None = None,
    ) -> BacktestAdapterOutput:
        spec = registry[strategy_id]
        resolved_parameters = resolve_backtest_parameters(strategy_id, parameters)
        golden_cross_uses_saved_signal_only = (
            strategy_id == "golden-cross"
            and resolved_parameters == {"short_window": 5.0, "long_window": 20.0}
            and DAILY_PRICES_INDICATORS not in datasets
        )
        if not golden_cross_uses_saved_signal_only:
            gate = build_run_readiness_gate([strategy_id], datasets, registry=registry)
            if not gate.can_run:
                raise BacktestDataReadinessError(gate)

        signal_rows = self._adapters[strategy_id](datasets, spec, resolved_parameters)
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
    parameters: Mapping[str, object] | None = None,
) -> pd.DataFrame:
    """Build normalized signal rows for one registered strategy."""

    return DEFAULT_BACKTEST_ADAPTER_REGISTRY.build_signal_rows(
        strategy_id,
        datasets,
        registry=registry,
        parameters=parameters,
    ).signal_rows


def _adapt_golden_cross(
    datasets: Mapping[str, pd.DataFrame | None],
    spec: BacktestStrategySpec,
    parameters: Mapping[str, float],
) -> pd.DataFrame:
    signal_frame = datasets.get(GOLDEN_CROSS_SIGNALS)
    if (
        parameters == {"short_window": 5.0, "long_window": 20.0}
        and signal_frame is not None
        and {"date", "close", "signal"}.issubset(signal_frame.columns)
    ):
        indicator_frame = datasets.get(DAILY_PRICES_INDICATORS)
        if indicator_frame is not None:
            _validate_saved_signal_alignment(signal_frame, indicator_frame)
        return _normalize_existing_signal_frame(signal_frame, spec, validated_alignment=indicator_frame is not None)

    frame = _prepare_price_frame(datasets.get(DAILY_PRICES_INDICATORS))
    result = frame.copy()
    short_window = int(parameters["short_window"])
    long_window = int(parameters["long_window"])
    short_column = f"ma_{short_window}"
    long_column = f"ma_{long_window}"
    if short_column not in result.columns:
        result[short_column] = result["close"].rolling(window=short_window, min_periods=short_window).mean()
    if long_column not in result.columns:
        result[long_column] = result["close"].rolling(window=long_window, min_periods=long_window).mean()
    strategy = GoldenCrossStrategy(short_column=short_column, long_column=long_column)
    result["signal"] = "hold"
    result["signal_reason"] = "At least two rows are required to detect a crossover."
    result["strategy_id"] = spec.strategy_id
    result["strategy_name"] = spec.strategy_name
    result[f"prev_{short_column}"] = result[short_column].shift(1)
    result[f"prev_{long_column}"] = result[long_column].shift(1)

    for index in range(1, len(result)):
        signal_result = strategy.evaluate_frame(result.iloc[index - 1 : index + 1])
        _apply_strategy_result(result, index, signal_result)

    return result


def _adapt_rsi(datasets: Mapping[str, pd.DataFrame | None], spec: BacktestStrategySpec, parameters: Mapping[str, float]) -> pd.DataFrame:
    return _apply_row_strategy(
        _prepare_price_frame(datasets[DAILY_PRICES_INDICATORS]),
        spec,
        RSIStrategy(buy_threshold=parameters["buy_threshold"], sell_threshold=parameters["sell_threshold"]),
    )


def _adapt_trend_filter(
    datasets: Mapping[str, pd.DataFrame | None],
    spec: BacktestStrategySpec,
    parameters: Mapping[str, float],
) -> pd.DataFrame:
    frame = _prepare_price_frame(datasets[DAILY_PRICES_INDICATORS])
    frame["prev_close"] = frame["close"].shift(1)
    return _apply_row_strategy(frame, spec, TrendFilterStrategy())


def _adapt_mean_reversion(
    datasets: Mapping[str, pd.DataFrame | None],
    spec: BacktestStrategySpec,
    parameters: Mapping[str, float],
) -> pd.DataFrame:
    return _apply_row_strategy(
        _prepare_price_frame(datasets[DAILY_PRICES_INDICATORS]),
        spec,
        MeanReversionStrategy(buy_ratio=parameters["buy_ratio"], sell_ratio=parameters["sell_ratio"]),
    )


def _adapt_disparity(
    datasets: Mapping[str, pd.DataFrame | None], spec: BacktestStrategySpec, parameters: Mapping[str, float]
) -> pd.DataFrame:
    return _apply_row_strategy(
        _prepare_price_frame(datasets[DAILY_PRICES_INDICATORS]),
        spec,
        DisparityStrategy(buy_below=parameters["buy_below"], sell_above=parameters["sell_above"]),
    )


def _adapt_momentum(datasets: Mapping[str, pd.DataFrame | None], spec: BacktestStrategySpec, parameters: Mapping[str, float]) -> pd.DataFrame:
    return _apply_row_strategy(
        _prepare_price_frame(datasets[DAILY_PRICES_INDICATORS]),
        spec,
        MomentumStrategy(buy_above=parameters["buy_above"], sell_below=parameters["sell_below"]),
    )


def _adapt_investor_flow(
    datasets: Mapping[str, pd.DataFrame | None],
    spec: BacktestStrategySpec,
    parameters: Mapping[str, float],
) -> pd.DataFrame:
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


def _validate_saved_signal_alignment(saved: pd.DataFrame, current: pd.DataFrame) -> None:
    """Reject saved default signals that do not describe the current prices."""
    require_unique_trading_dates(saved, source=GOLDEN_CROSS_SIGNALS)
    require_unique_trading_dates(current, source=DAILY_PRICES_INDICATORS)
    saved_prices = _alignment_prices(saved, GOLDEN_CROSS_SIGNALS)
    current_prices = _alignment_prices(current, DAILY_PRICES_INDICATORS)
    missing = sorted(set(current_prices.index) - set(saved_prices.index))
    extra = sorted(set(saved_prices.index) - set(current_prices.index))
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing saved dates: {', '.join(value.isoformat() for value in missing[:3])}")
        if extra:
            details.append(f"extra saved dates: {', '.join(value.isoformat() for value in extra[:3])}")
        raise ValueError(
            f"{GOLDEN_CROSS_SIGNALS} trading dates do not match {DAILY_PRICES_INDICATORS}; " + "; ".join(details)
        )
    mismatches = saved_prices.reindex(current_prices.index).ne(current_prices)
    if mismatches.any():
        sample = ", ".join(value.isoformat() for value in sorted(current_prices.index[mismatches])[:3])
        raise ValueError(f"{GOLDEN_CROSS_SIGNALS} close mismatch with {DAILY_PRICES_INDICATORS} for trading dates: {sample}")


def _alignment_prices(frame: pd.DataFrame, source: str) -> pd.Series:
    dates = local_trading_dates(frame["date"])
    if dates.isna().any():
        raise ValueError(f"{source} has invalid trading dates; cannot verify saved signal alignment")
    raw_prices = frame["close"].reset_index(drop=True)
    unsupported = raw_prices.map(lambda value: isinstance(value, (bool, complex, date)))
    prices = pd.to_numeric(raw_prices.mask(unsupported), errors="coerce")
    valid = prices.notna() & prices.gt(0) & prices.lt(float("inf"))
    if not valid.all():
        sample = ", ".join(value.isoformat() for value in sorted(dates[~valid])[:3])
        raise ValueError(f"{source} has invalid close values for trading dates: {sample}; expected positive finite numeric close")
    return pd.Series(prices.to_numpy(), index=dates.to_numpy())


def _normalize_existing_signal_frame(
    frame: pd.DataFrame, spec: BacktestStrategySpec, *, validated_alignment: bool = False
) -> pd.DataFrame:
    require_unique_trading_dates(frame, source=GOLDEN_CROSS_SIGNALS)
    result = frame.copy()
    try:
        parsed = pd.to_datetime(result["date"], errors="coerce")
    except (TypeError, ValueError):
        if not validated_alignment:
            raise
        parsed = pd.to_datetime(local_trading_dates(frame["date"]))
    if validated_alignment and (parsed.isna().any() or parsed.dtype == object):
        # Alignment proved every original date valid. Do not lose mixed-offset
        # rows in downstream datetime parsing: use their verified local days.
        parsed = pd.to_datetime(local_trading_dates(frame["date"]))
    result["date"] = parsed.to_numpy()
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
