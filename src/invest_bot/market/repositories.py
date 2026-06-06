from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pandas as pd

from invest_bot.market.storage import SavedDataset


class DatasetStorage(Protocol):
    """Persistence contract for saving and locating named datasets."""

    root_dir: Path

    def save(self, dataset: str, filename: str, frame: pd.DataFrame) -> SavedDataset:
        """Persist a dataset frame and return the saved artifact metadata."""


class StockMasterRepositoryProtocol(Protocol):
    """Contract for loading and refreshing stock master reference entries."""

    def load_entries(self) -> list[dict[str, str]]:
        """Return normalized stock master entries."""

    def ensure_updated(self, force: bool = False) -> Path:
        """Refresh the backing source when needed and return the local path."""
