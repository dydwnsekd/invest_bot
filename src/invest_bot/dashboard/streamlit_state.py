from __future__ import annotations

from pathlib import Path

import pandas as pd

from invest_bot.dashboard.service import DashboardDataService, DatasetPreview
from invest_bot.jobs.scheduled_collection import load_schedule_status


def load_optional_schedule_status():
    try:
        return load_schedule_status()
    except (FileNotFoundError, ValueError):
        return None


def read_preview_frame(service: DashboardDataService, source: DatasetPreview | Path) -> pd.DataFrame:
    if isinstance(source, DatasetPreview):
        return service.load_preview_frame(source)
    try:
        return pd.read_csv(source)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def load_indicator_frame_for_symbol(service: DashboardDataService, symbol: str) -> pd.DataFrame | None:
    storage = service.get_dataset_storage()
    filename = None
    if storage is not None:
        filename = storage.latest_filename("daily_prices_indicators", symbol)
    else:
        indicator_dir = service.processed_root / "daily_prices_indicators"
        if not indicator_dir.exists():
            return None
        matches = sorted(indicator_dir.glob(f"{symbol}_*.csv"), key=lambda item: item.stat().st_mtime, reverse=True)
        if matches:
            filename = matches[0].name
    if filename is None:
        return None
    try:
        frame = (
            storage.load("daily_prices_indicators", filename)
            if storage is not None
            else pd.read_csv(service.processed_root / "daily_prices_indicators" / filename)
        )
        return frame
    except (pd.errors.EmptyDataError, FileNotFoundError):
        return None
