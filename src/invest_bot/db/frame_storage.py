from __future__ import annotations

import re
from datetime import UTC, date, datetime
from numbers import Number
from pathlib import Path

import pandas as pd

from invest_bot.config.settings import AppSettings
from invest_bot.db.contracts import DatasetFrameRecord
from invest_bot.db.engine import build_engine, build_session_factory
from invest_bot.db.repositories import (
    SqlAlchemyDatasetFrameRepository,
    frame_from_json,
    frame_to_json,
    normalize_symbol,
)


class DbFrameStorage:
    """Persist tabular datasets as DB snapshots instead of local CSV files."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.root_dir = Path("/virtual/db/dataset_frames")
        engine = build_engine(database_url)
        self.repository = SqlAlchemyDatasetFrameRepository(build_session_factory(engine))

    @classmethod
    def from_settings(cls, settings: AppSettings | None = None) -> "DbFrameStorage":
        resolved = settings or AppSettings.from_file()
        return cls(resolved.database_url)

    def save(self, dataset: str, filename: str, frame: pd.DataFrame) -> "SavedDataset":
        from invest_bot.market.storage import SavedDataset

        symbol = self._resolve_symbol(frame, filename)
        as_of_date = self._resolve_as_of_date(frame)
        self.repository.save(
            DatasetFrameRecord(
                dataset=dataset,
                filename=filename,
                frame_json=frame_to_json(frame),
                row_count=len(frame),
                created_at=datetime.now(UTC),
                symbol=symbol,
                as_of_date=as_of_date,
            )
        )
        return SavedDataset(dataset=dataset, path=self.root_dir / dataset / filename, rows=len(frame))

    def load(self, dataset: str, filename: str) -> pd.DataFrame:
        record = self.repository.load(dataset, filename)
        if record is None:
            raise FileNotFoundError(f"Dataset snapshot not found for dataset='{dataset}', filename='{filename}'")
        return frame_from_json(record.frame_json)

    def latest_filename(self, dataset: str, symbol: str) -> str | None:
        record = self.repository.latest_for_symbol(dataset, symbol)
        return record.filename if record is not None else None

    @staticmethod
    def _resolve_symbol(frame: pd.DataFrame, filename: str) -> str:
        if not frame.empty:
            for column in ("symbol", "pdno"):
                if column in frame.columns:
                    value = str(frame.iloc[0].get(column, "")).strip()
                    if value:
                        return normalize_symbol(value)
        stem = Path(filename).stem
        symbol = stem.split("_", 1)[0]
        return normalize_symbol(symbol) if symbol else ""

    @staticmethod
    def _resolve_as_of_date(frame: pd.DataFrame) -> date | None:
        if frame.empty:
            return None
        for column in ("date", "trade_date", "stck_bsop_date"):
            if column not in frame.columns:
                continue
            parsed = [_parse_snapshot_date(value) for value in frame[column]]
            valid_dates = [value for value in parsed if value is not None]
            if valid_dates:
                return max(valid_dates)
        return None


def _parse_snapshot_date(value: object) -> date | None:
    """Read a local calendar day without interpreting numeric values as epochs."""
    if not pd.api.types.is_scalar(value):
        return None
    if value is None or pd.isna(value) or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        if re.fullmatch(r"[0-9]{8}(?:\.0+)?", text):
            return datetime.strptime(text.split(".")[0], "%Y%m%d").date()
        if isinstance(value, Number) or re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", text):
            return None
        parsed = pd.to_datetime(text, errors="coerce")
        return None if pd.isna(parsed) else parsed.date()
    except (TypeError, ValueError, OverflowError):
        return None
