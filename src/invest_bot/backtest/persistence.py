from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from .combination import BacktestCombinationSettings, resolve_backtest_combination_settings
from .parameters import resolve_backtest_parameters
from invest_bot.backtest.strategy_registry import DAILY_PRICES_INDICATORS, INVESTOR_DAILY
from .strategy_registry import BACKTEST_STRATEGY_SPECS

GOLDEN_CROSS_SIGNALS = "golden_cross_signals"
DAILY_PRICES = "daily_prices"
BACKTEST_TRADES_OUTPUT = "backtest_trades"
BACKTEST_SUMMARY_OUTPUT = "backtest_summary"
COMBINATION_METADATA_VERSION = 1

SUMMARY_PROVENANCE_COLUMNS = (
    "indicator_source_dataset",
    "indicator_source_filename",
    "signal_source_dataset",
    "signal_source_filename",
    "investor_source_dataset",
    "investor_source_filename",
    "price_source_dataset",
    "price_source_filename",
    "input_sources_json",
    "strategy_parameters_json",
    "combination_settings_json",
)


@dataclass(frozen=True, slots=True)
class BacktestInputSources:
    indicator_source_dataset: str | None = DAILY_PRICES_INDICATORS
    indicator_source_filename: str | None = None
    signal_source_dataset: str | None = GOLDEN_CROSS_SIGNALS
    signal_source_filename: str | None = None
    investor_source_dataset: str | None = INVESTOR_DAILY
    investor_source_filename: str | None = None
    price_source_dataset: str | None = DAILY_PRICES
    price_source_filename: str | None = None

    def as_json(self) -> str:
        payload = {
            "indicator": {
                "dataset": self.indicator_source_dataset,
                "filename": self.indicator_source_filename,
            },
            "signal": {
                "dataset": self.signal_source_dataset,
                "filename": self.signal_source_filename,
            },
            "investor": {
                "dataset": self.investor_source_dataset,
                "filename": self.investor_source_filename,
            },
            "price": {
                "dataset": self.price_source_dataset,
                "filename": self.price_source_filename,
            },
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True, slots=True)
class BacktestPersistenceContext:
    timestamp_slug: str
    run_group_id: str
    run_id: str
    symbol: str
    strategy_id: str
    strategy_name: str
    input_sources: BacktestInputSources
    strategy_parameters: Mapping[str, float]
    combination_settings: Mapping[str, Any]

    def strategy_parameters_json(self) -> str:
        return json.dumps(dict(self.strategy_parameters), ensure_ascii=False, sort_keys=True)

    def combination_settings_json(self) -> str:
        return json.dumps(dict(self.combination_settings), ensure_ascii=False, sort_keys=True)


def build_timestamp_slug(now: datetime) -> str:
    return now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def build_context(
    *,
    symbol: str,
    strategy_id: str,
    strategy_name: str,
    input_sources: BacktestInputSources,
    strategy_parameters: Mapping[str, float] | None = None,
    combination_settings: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> BacktestPersistenceContext:
    resolved_now = now or datetime.now(UTC)
    timestamp_slug = build_timestamp_slug(resolved_now)
    settings = dict(combination_settings or {})
    if "metadata_version" in settings or "components" in settings:
        recorded = read_combination_metadata(settings)
        if recorded.status != "recorded" or recorded.metadata is None:
            raise ValueError(recorded.message)
        settings = recorded.metadata
    return BacktestPersistenceContext(
        timestamp_slug=timestamp_slug,
        run_group_id=f"backtest_group_{timestamp_slug}",
        run_id=f"{symbol}_{strategy_id}_{timestamp_slug}",
        symbol=symbol,
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        input_sources=input_sources,
        strategy_parameters=dict(strategy_parameters or {}),
        combination_settings=settings,
    )


@dataclass(frozen=True, slots=True)
class CombinationMetadataRead:
    status: str
    metadata: dict[str, Any] | None
    message: str


def build_combination_metadata(
    settings: BacktestCombinationSettings,
    components: Mapping[str, BacktestPersistenceContext],
) -> dict[str, Any]:
    """Capture completed adapter contexts; callers must supply actual sources.

    Parameters must already be fully resolved for that execution. This does not
    rerun adapters or discover source files, and is not an old-artifact repair.
    """
    ids = list(settings.weights)
    if set(ids) != set(components):
        raise ValueError("Combination components must match selected strategy IDs.")
    resolved = resolve_backtest_combination_settings(ids, settings.mode, settings.weights)
    if len({(context.symbol, context.run_group_id) for context in components.values()}) != 1:
        raise ValueError("Combination contexts must belong to one symbol and execution group.")
    payload: dict[str, Any] = {
        "metadata_version": COMBINATION_METADATA_VERSION, "mode": resolved.mode,
        "weights": dict(resolved.weights), "component_strategy_ids": ids, "components": {},
    }
    for strategy_id in ids:
        context = components[strategy_id]
        if strategy_id not in BACKTEST_STRATEGY_SPECS or context.strategy_id != strategy_id:
            raise ValueError("Component context strategy ID does not match its key.")
        parameters = dict(context.strategy_parameters)
        if set(parameters) != set(resolve_backtest_parameters(strategy_id, parameters)):
            raise ValueError("Component parameters must contain the complete effective settings.")
        sources = json.loads(context.input_sources.as_json())
        payload["components"][strategy_id] = {
            "strategy_parameters": parameters, "input_sources": sources,
            "uses_saved_signal": sources["signal"]["dataset"] is not None,
        }
    recorded = read_combination_metadata(payload)
    if recorded.status != "recorded" or recorded.metadata is None:
        raise ValueError(recorded.message)
    return recorded.metadata


def read_combination_metadata(value: object) -> CombinationMetadataRead:
    """Read stored evidence, never filling missing history from today's defaults."""
    if value is None or value is pd.NA or value is pd.NaT or (isinstance(value, float) and pd.isna(value)):
        value = {}
    try:
        data = json.loads(value) if isinstance(value, str) and value.strip() else value
        if isinstance(value, str) and not value.strip():
            data = {}
        if not isinstance(data, dict):
            raise ValueError("metadata must be a JSON object")
        if "metadata_version" not in data:
            if "components" in data:
                raise ValueError("components have no metadata version")
            return CombinationMetadataRead("legacy", None, "구형 조합: 구성별 설정·출처 기록 없음 (추정하지 않음)")
        version = data["metadata_version"]
        if type(version) is not int:
            raise ValueError("metadata_version must be an integer")
        if version != COMBINATION_METADATA_VERSION:
            return CombinationMetadataRead("unsupported", None, f"미지원 조합 metadata 버전: {version}")
        # A detached, finite, JSON-only snapshot; validation below is versioned
        # structure, not today's parameter defaults, bounds or source discovery.
        data = json.loads(json.dumps(data, allow_nan=False))
        _validate_combination_v1(data)
        return CombinationMetadataRead("recorded", data, "구성별 실행 설정·출처 기록됨")
    except (TypeError, ValueError, KeyError, OverflowError) as error:
        return CombinationMetadataRead("malformed", None, f"잘못된 조합 metadata: {error}")


def _validate_combination_v1(data: dict[str, Any]) -> None:
    ids, weights, components = data["component_strategy_ids"], data["weights"], data["components"]
    if (data["mode"] not in ("and", "or", "weighted") or not isinstance(ids, list) or len(ids) < 2
            or not all(isinstance(key, str) and key.strip() for key in ids) or len(set(ids)) != len(ids)
            or not isinstance(weights, dict) or not isinstance(components, dict)
            or set(ids) != set(weights) or set(ids) != set(components)):
        raise ValueError("mode, weights and components disagree")
    for strategy_id in ids:
        weight, component = weights[strategy_id], components[strategy_id]
        if type(weight) not in (int, float) or not isfinite(weight) or weight <= 0 or not isinstance(component, dict):
            raise ValueError("invalid component or weight")
        parameters, sources = component["strategy_parameters"], component["input_sources"]
        if (not isinstance(parameters, dict) or not all(
            isinstance(key, str) and key.strip() and type(value) in (int, float) and isfinite(value)
            for key, value in parameters.items()
        )):
            raise ValueError("invalid recorded parameters")
        if not isinstance(sources, dict) or set(sources) != {"indicator", "signal", "investor", "price"}:
            raise ValueError("invalid input source map")
        for source in sources.values():
            if not isinstance(source, dict) or set(source) != {"dataset", "filename"}:
                raise ValueError("invalid source pair")
            pair = (source["dataset"], source["filename"])
            if pair != (None, None) and not all(isinstance(item, str) and item.strip() for item in pair):
                raise ValueError("source dataset/filename must both be recorded or both absent")
        used = component["uses_saved_signal"]
        signal = sources["signal"]
        if type(used) is not bool or used != (signal["dataset"] is not None):
            raise ValueError("saved signal flag disagrees with recorded source")
        if used and (strategy_id != "golden-cross" or signal["dataset"] != GOLDEN_CROSS_SIGNALS
                     or parameters != {"short_window": 5, "long_window": 20}):
            raise ValueError("saved signal source disagrees with component settings")


def attach_input_sources(frame: pd.DataFrame, input_sources: BacktestInputSources) -> pd.DataFrame:
    result = frame.copy()
    result.attrs["backtest_input_sources"] = input_sources
    return result


def input_sources_from_frame(frame: pd.DataFrame) -> BacktestInputSources:
    value = frame.attrs.get("backtest_input_sources")
    if isinstance(value, BacktestInputSources):
        return value
    return BacktestInputSources()


def enrich_trades(frame: pd.DataFrame, context: BacktestPersistenceContext) -> pd.DataFrame:
    result = frame.copy()
    result.attrs["backtest_context"] = context
    result["run_group_id"] = context.run_group_id
    result["run_id"] = context.run_id
    result["symbol"] = context.symbol
    result["strategy_id"] = context.strategy_id
    result["strategy_name"] = context.strategy_name
    result["strategy_parameters_json"] = context.strategy_parameters_json()
    result["combination_settings_json"] = context.combination_settings_json()
    result["output_type"] = BACKTEST_TRADES_OUTPUT
    return result


def enrich_summary(frame: pd.DataFrame, context: BacktestPersistenceContext) -> pd.DataFrame:
    result = frame.copy()
    result.attrs["backtest_context"] = context
    result["run_group_id"] = context.run_group_id
    result["run_id"] = context.run_id
    result["symbol"] = context.symbol
    result["strategy_id"] = context.strategy_id
    result["strategy_name"] = context.strategy_name
    result["strategy_parameters_json"] = context.strategy_parameters_json()
    result["combination_settings_json"] = context.combination_settings_json()
    result["output_type"] = BACKTEST_SUMMARY_OUTPUT
    result["indicator_source_dataset"] = context.input_sources.indicator_source_dataset
    result["indicator_source_filename"] = context.input_sources.indicator_source_filename
    result["signal_source_dataset"] = context.input_sources.signal_source_dataset
    result["signal_source_filename"] = context.input_sources.signal_source_filename
    result["investor_source_dataset"] = context.input_sources.investor_source_dataset
    result["investor_source_filename"] = context.input_sources.investor_source_filename
    result["price_source_dataset"] = context.input_sources.price_source_dataset
    result["price_source_filename"] = context.input_sources.price_source_filename
    result["input_sources_json"] = context.input_sources.as_json()
    return result


def build_output_filename(frame: pd.DataFrame, output_type: str, fallback_source_filename: str | None = None) -> str:
    context = frame.attrs.get("backtest_context")
    symbol = _first_value(frame, "symbol") or getattr(context, "symbol", None) or _symbol_from_filename(fallback_source_filename)
    strategy_id = _first_value(frame, "strategy_id") or getattr(context, "strategy_id", None) or "golden-cross"
    run_id = _first_value(frame, "run_id") or getattr(context, "run_id", None)
    timestamp_slug = (
        _timestamp_from_run_id(run_id)
        or getattr(context, "timestamp_slug", None)
        or _timestamp_from_filename(fallback_source_filename)
    )
    if not symbol or not timestamp_slug:
        raise ValueError("Cannot build backtest output filename without symbol and timestamp information.")
    return f"{symbol}_{strategy_id}_{timestamp_slug}_{output_type}.csv"


def _first_value(frame: pd.DataFrame, column: str) -> str | None:
    if column not in frame.columns:
        return None
    non_null = frame[column].dropna()
    if non_null.empty:
        return None
    value = str(non_null.iloc[0]).strip()
    return value or None


def _symbol_from_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    stem = Path(filename).stem
    symbol = stem.split("_", 1)[0].strip()
    return symbol or None


def _timestamp_from_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    parts = Path(filename).stem.split("_")
    for part in reversed(parts):
        if len(part) == 16 and part.endswith("Z") and "T" in part:
            return part
    return None


def _timestamp_from_run_id(run_id: str | None) -> str | None:
    if not run_id:
        return None
    parts = str(run_id).rsplit("_", 1)
    if len(parts) != 2:
        return None
    candidate = parts[1].strip()
    return candidate if len(candidate) == 16 and candidate.endswith("Z") and "T" in candidate else None


def coerce_input_sources(data: dict[str, Any]) -> BacktestInputSources:
    return BacktestInputSources(
        indicator_source_dataset=data.get("indicator_source_dataset", DAILY_PRICES_INDICATORS),
        indicator_source_filename=data.get("indicator_source_filename"),
        signal_source_dataset=data.get("signal_source_dataset", GOLDEN_CROSS_SIGNALS),
        signal_source_filename=data.get("signal_source_filename"),
        investor_source_dataset=data.get("investor_source_dataset", INVESTOR_DAILY),
        investor_source_filename=data.get("investor_source_filename"),
        price_source_dataset=data.get("price_source_dataset", DAILY_PRICES),
        price_source_filename=data.get("price_source_filename"),
    )
