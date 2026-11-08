"""Explicit, preflighted saving of completed backtest batches (no execution)."""

from __future__ import annotations

from datetime import datetime
import json
from math import isfinite
import re

import pandas as pd

from invest_bot.market.repositories import DatasetStorage
from invest_bot.market.storage import SavedDataset
from .persistence import BACKTEST_SUMMARY_OUTPUT, BACKTEST_TRADES_OUTPUT, build_output_filename, read_combination_metadata


IDENTITY_COLUMNS = ("run_group_id", "run_id", "symbol", "strategy_id", "strategy_name")
METADATA_COLUMNS = ("strategy_parameters_json", "combination_settings_json")


class BacktestArtifactSaveError(RuntimeError):
    """A backend write failed; saved contains only confirmed returned writes."""

    def __init__(self, saved: tuple[SavedDataset, ...], dataset: str, filename: str, cause: Exception) -> None:
        self.saved, self.failed_dataset, self.failed_filename = saved, dataset, filename
        super().__init__(f"Backtest save failed at {dataset}/{filename}; partial artifacts may exist: {cause}")


def save_backtest_batch(
    storage: DatasetStorage, summary_frame: pd.DataFrame, trade_frame: pd.DataFrame,
) -> tuple[SavedDataset, ...]:
    """Save only on explicit invocation; refuse known existing run artifacts.

    All input/collision checks precede writes. Storage has no batch transaction
    or exclusive-create primitive: callers must serialize saves. A concurrent
    external writer can race preflight; failures cannot be rolled back here.
    """
    required = {*IDENTITY_COLUMNS, *METADATA_COLUMNS, "output_type", "trade_count", "input_sources_json",
                "total_return_pct", "max_drawdown_pct", "final_equity"}
    if summary_frame.empty or not required.issubset(summary_frame.columns):
        raise ValueError("Completed summary rows with identity, metadata and metrics are required.")
    if summary_frame.run_id.duplicated().any():
        raise ValueError("Each run must have exactly one summary row.")
    if not trade_frame.empty:
        needed = {*IDENTITY_COLUMNS, *METADATA_COLUMNS, "output_type", "entry_date", "exit_date",
                  "entry_price", "exit_price", "return_pct"}
        if not needed.issubset(trade_frame.columns) or not trade_frame.run_id.isin(summary_frame.run_id).all():
            raise ValueError("Trade rows must belong to the supplied complete summaries.")

    planned: list[tuple[str, str, pd.DataFrame]] = []
    for _, summary in summary_frame.iterrows():
        _validate_identity(summary)
        if summary.output_type != BACKTEST_SUMMARY_OUTPUT:
            raise ValueError("Invalid summary output_type.")
        for column in ("total_return_pct", "max_drawdown_pct", "final_equity"):
            if not isfinite(float(summary[column])):
                raise ValueError(f"Invalid summary metric: {column}")
        parameters = _json_object(summary.strategy_parameters_json)
        combination = _json_object(summary.combination_settings_json)
        _json_object(summary.input_sources_json)
        if summary.strategy_id.startswith("combination-"):
            recorded = read_combination_metadata(combination)
            if recorded.status != "recorded" or recorded.metadata is None:
                raise ValueError(recorded.message)
            if summary.strategy_id != f"combination-{recorded.metadata['mode']}":
                raise ValueError("Combination mode disagrees with run identity.")
        run_trades = trade_frame.loc[trade_frame.run_id == summary.run_id].copy() if not trade_frame.empty else trade_frame.copy()
        count = float(summary.trade_count)
        if isinstance(summary.trade_count, bool) or not isfinite(count) or count != len(run_trades):
            raise ValueError("Summary trade_count disagrees with its trade rows.")
        for _, trade in run_trades.iterrows():
            if any(trade[column] != summary[column] for column in IDENTITY_COLUMNS) or trade.output_type != BACKTEST_TRADES_OUTPUT:
                raise ValueError("Trade identity disagrees with its summary.")
            if _json_object(trade.strategy_parameters_json) != parameters or _json_object(trade.combination_settings_json) != combination:
                raise ValueError("Trade metadata disagrees with its summary.")
        if run_trades.empty:
            # Metadata/identity values live in the summary; do not fabricate a
            # trade row. Even a no-column input produces a readable CSV header.
            for column in (*IDENTITY_COLUMNS, *METADATA_COLUMNS, "output_type"):
                run_trades[column] = pd.Series(dtype="object")
        run_summary = summary.to_frame().T
        for dataset, kind, frame in (
            ("backtest_summaries", BACKTEST_SUMMARY_OUTPUT, run_summary),
            ("backtest_trades", BACKTEST_TRADES_OUTPUT, run_trades),
        ):
            filename = build_output_filename(run_summary, kind)
            frame.attrs = {}
            planned.append((dataset, filename, frame))

    for dataset, filename, _ in planned:
        try:
            storage.load(dataset, filename)
        except FileNotFoundError:
            continue
        except pd.errors.EmptyDataError:
            pass  # a zero-byte existing artifact is still an existing artifact
        raise FileExistsError(f"Backtest artifact already exists: {dataset}/{filename}")
    saved: list[SavedDataset] = []
    for dataset, filename, frame in planned:
        try:
            saved.append(storage.save(dataset, filename, frame))
        except Exception as error:
            raise BacktestArtifactSaveError(tuple(saved), dataset, filename, error) from error
    return tuple(saved)


def _validate_identity(row: pd.Series) -> None:
    if not all(isinstance(row[column], str) and row[column].strip() for column in IDENTITY_COLUMNS):
        raise ValueError("Run identity must contain nonempty strings.")
    if not all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", row[column]) for column in ("symbol", "strategy_id")):
        raise ValueError("Unsafe symbol or strategy ID in artifact filename.")
    timestamp = row.run_id.rsplit("_", 1)[-1]
    if len(timestamp) != 16:
        raise ValueError("Invalid run timestamp.")
    datetime.strptime(timestamp, "%Y%m%dT%H%M%SZ")
    if row.run_id != f"{row.symbol}_{row.strategy_id}_{timestamp}" or row.run_group_id != f"backtest_group_{timestamp}":
        raise ValueError("Inconsistent run identity.")


def _json_object(value: object) -> dict:
    try:
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("expected object")
        json.dumps(parsed, allow_nan=False)
        return parsed
    except (TypeError, ValueError) as error:
        raise ValueError("Artifact metadata must be finite JSON objects.") from error
