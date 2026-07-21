from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

import pandas as pd
from pandas.errors import EmptyDataError

from invest_bot.backtest import DEFAULT_BACKTEST_RUNNER, GOLDEN_CROSS_SIGNALS, build_strategy_signal_rows
from invest_bot.backtest.persistence import (
    BACKTEST_SUMMARY_OUTPUT,
    BACKTEST_TRADES_OUTPUT,
    BacktestInputSources,
    DAILY_PRICES,
    BacktestPersistenceContext,
    attach_input_sources,
    build_context,
    build_output_filename,
    enrich_summary,
    enrich_trades,
    input_sources_from_frame,
)
from invest_bot.backtest.runner import BacktestResult
from invest_bot.backtest.strategy_registry import DAILY_PRICES_INDICATORS, INVESTOR_DAILY
from invest_bot.config.settings import AppSettings
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.market.repositories import DatasetStorage
from invest_bot.market.storage import SavedDataset


@dataclass(slots=True)
class BacktestRequest:
    symbol: str
    source_filename: str
    indicator_filename: str | None = None
    investor_filename: str | None = None
    price_filename: str | None = None


class GoldenCrossBacktestGenerator:
    """Draft backtest runner for golden cross signals."""

    def __init__(
        self,
        processed_storage: DatasetStorage | None = None,
        settings: AppSettings | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.processed_storage = processed_storage or DbFrameStorage.from_settings(settings)
        self.now_fn = now_fn or (lambda: datetime.now(UTC))
        self._contexts_by_key: dict[tuple[str, str, str], BacktestPersistenceContext] = {}

    def load_signal_frame(self, request: BacktestRequest) -> pd.DataFrame:
        try:
            frame = self.processed_storage.load(GOLDEN_CROSS_SIGNALS, request.source_filename)
        except EmptyDataError:
            frame = pd.DataFrame(columns=["date", "close", "signal"])
        signal_rows = build_strategy_signal_rows("golden-cross", {GOLDEN_CROSS_SIGNALS: frame})
        return attach_input_sources(
            signal_rows,
            BacktestInputSources(
                indicator_source_dataset=DAILY_PRICES_INDICATORS if request.indicator_filename else None,
                indicator_source_filename=request.indicator_filename,
                signal_source_dataset=GOLDEN_CROSS_SIGNALS,
                signal_source_filename=request.source_filename,
                investor_source_dataset=INVESTOR_DAILY if request.investor_filename else None,
                investor_source_filename=request.investor_filename,
                price_source_dataset=DAILY_PRICES if request.price_filename else None,
                price_source_filename=request.price_filename,
            ),
        )

    def run_backtest(self, symbol: str, signal_frame: pd.DataFrame) -> BacktestResult:
        result = DEFAULT_BACKTEST_RUNNER.run(symbol, signal_frame)
        context = self._context_for_run(symbol, signal_frame, result.summary)
        return BacktestResult(
            trades=enrich_trades(result.trades, context),
            summary=enrich_summary(result.summary, context),
        )

    def save_trades(self, source_filename: str, trades: pd.DataFrame) -> SavedDataset:
        trades_to_save = self._ensure_output_frame(trades, source_filename, BACKTEST_TRADES_OUTPUT)
        filename = build_output_filename(trades_to_save, BACKTEST_TRADES_OUTPUT, source_filename)
        return self.processed_storage.save("backtest_trades", filename, trades_to_save)

    def save_summary(self, source_filename: str, summary: pd.DataFrame) -> SavedDataset:
        summary_to_save = self._ensure_output_frame(summary, source_filename, BACKTEST_SUMMARY_OUTPUT)
        filename = build_output_filename(summary_to_save, BACKTEST_SUMMARY_OUTPUT, source_filename)
        return self.processed_storage.save("backtest_summaries", filename, summary_to_save)

    def _ensure_output_frame(self, frame: pd.DataFrame, source_filename: str, output_type: str) -> pd.DataFrame:
        if {"run_group_id", "run_id", "symbol", "strategy_id", "strategy_name", "output_type"}.issubset(frame.columns):
            return frame.copy()

        symbol = _first_value(frame, "symbol") or request_symbol_from_filename(source_filename)
        strategy_id = _first_value(frame, "strategy_id") or "golden-cross"
        strategy_name = _first_value(frame, "strategy_name") or "Golden Cross"
        context = self._context_for_parts(
            source_filename=source_filename,
            symbol=symbol,
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            input_sources=input_sources_from_frame(frame),
        )
        return enrich_summary(frame, context) if output_type == BACKTEST_SUMMARY_OUTPUT else enrich_trades(frame, context)

    def _context_for_run(self, symbol: str, signal_frame: pd.DataFrame, summary_frame: pd.DataFrame) -> BacktestPersistenceContext:
        strategy_id = _first_value(summary_frame, "strategy_id") or _first_value(signal_frame, "strategy_id") or "golden-cross"
        strategy_name = _first_value(summary_frame, "strategy_name") or _first_value(signal_frame, "strategy_name") or "Golden Cross"
        source_filename = input_sources_from_frame(signal_frame).signal_source_filename or f"{symbol}.csv"
        return self._context_for_parts(
            source_filename=source_filename,
            symbol=symbol,
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            input_sources=input_sources_from_frame(signal_frame),
        )

    def _context_for_parts(
        self,
        *,
        source_filename: str,
        symbol: str,
        strategy_id: str,
        strategy_name: str,
        input_sources: BacktestInputSources,
    ) -> BacktestPersistenceContext:
        key = (source_filename, symbol, strategy_id)
        existing = self._contexts_by_key.get(key)
        if existing is not None:
            return existing
        context = build_context(
            symbol=symbol,
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            input_sources=input_sources,
            now=self.now_fn(),
        )
        self._contexts_by_key[key] = context
        return context


def request_symbol_from_filename(source_filename: str) -> str:
    return source_filename.split("_", 1)[0]


def _first_value(frame: pd.DataFrame, column: str) -> str | None:
    if column not in frame.columns:
        return None
    non_null = frame[column].dropna()
    if non_null.empty:
        return None
    value = str(non_null.iloc[0]).strip()
    return value or None
