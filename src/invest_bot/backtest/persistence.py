from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from invest_bot.backtest.strategy_registry import DAILY_PRICES_INDICATORS, INVESTOR_DAILY

GOLDEN_CROSS_SIGNALS = "golden_cross_signals"
DAILY_PRICES = "daily_prices"
BACKTEST_TRADES_OUTPUT = "backtest_trades"
BACKTEST_SUMMARY_OUTPUT = "backtest_summary"

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


def build_timestamp_slug(now: datetime) -> str:
    return now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def build_context(
    *,
    symbol: str,
    strategy_id: str,
    strategy_name: str,
    input_sources: BacktestInputSources,
    now: datetime | None = None,
) -> BacktestPersistenceContext:
    resolved_now = now or datetime.now(UTC)
    timestamp_slug = build_timestamp_slug(resolved_now)
    return BacktestPersistenceContext(
        timestamp_slug=timestamp_slug,
        run_group_id=f"backtest_group_{timestamp_slug}",
        run_id=f"{symbol}_{strategy_id}_{timestamp_slug}",
        symbol=symbol,
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        input_sources=input_sources,
    )


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
