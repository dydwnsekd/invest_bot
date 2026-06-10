from __future__ import annotations

from pathlib import Path

import pandas as pd

from invest_bot.dashboard.service import DashboardDataService
from invest_bot.jobs.scheduled_collection import load_schedule_status


def load_optional_schedule_status():
    try:
        return load_schedule_status()
    except (FileNotFoundError, ValueError):
        return None


def read_preview_frame(path: Path) -> pd.DataFrame:
    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    return frame


def load_indicator_frame_for_symbol(symbol: str) -> pd.DataFrame | None:
    service = DashboardDataService()
    indicator_dir = service.processed_root / "daily_prices_indicators"
    if not indicator_dir.exists():
        return None
    matches = sorted(indicator_dir.glob(f"{symbol}_*.csv"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not matches:
        return None
    try:
        return pd.read_csv(matches[0])
    except pd.errors.EmptyDataError:
        return None
