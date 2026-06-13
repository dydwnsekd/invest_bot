from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Protocol

import pandas as pd

from invest_bot.market.storage import SavedDataset


class DatasetStorage(Protocol):
    root_dir: Path

    def save(self, dataset: str, filename: str, frame: pd.DataFrame) -> SavedDataset:
        ...

    def load(self, dataset: str, filename: str) -> pd.DataFrame:
        ...

    def latest_filename(self, dataset: str, symbol: str) -> str | None:
        ...


class MarketDataWriter(Protocol):
    def save_daily_prices(
        self, symbol: str, start_date: date, end_date: date, summary: pd.DataFrame, prices: pd.DataFrame
    ) -> None: ...

    def save_stock_info(self, symbol: str, stock_info: pd.DataFrame) -> None: ...

    def save_investor_daily(
        self, symbol: str, target_date: date, investor_daily: pd.DataFrame, investor_summary: pd.DataFrame
    ) -> None: ...


class StockMasterRepositoryProtocol(Protocol):
    def load_entries(self) -> list[dict[str, str]]:
        ...

    def ensure_updated(self, force: bool = False) -> Path:
        ...
