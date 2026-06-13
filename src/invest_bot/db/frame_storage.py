from __future__ import annotations

from datetime import UTC, datetime
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
    def _resolve_as_of_date(frame: pd.DataFrame):
        if frame.empty:
            return None
        for column in ("date", "trade_date", "stck_bsop_date"):
            if column not in frame.columns:
                continue
            value = frame.iloc[-1].get(column)
            if value in (None, ""):
                continue
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.isna(parsed):
                continue
            return parsed.date()
        return None
