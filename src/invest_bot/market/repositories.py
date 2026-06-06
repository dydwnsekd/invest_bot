from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pandas as pd

from invest_bot.market.storage import SavedDataset


class DatasetStorage(Protocol):
    root_dir: Path

    def save(self, dataset: str, filename: str, frame: pd.DataFrame) -> SavedDataset: ...


class SymbolMasterRepository(Protocol):
    def load_entries(self) -> list[dict[str, str]]: ...

    def ensure_updated(self, force: bool = False) -> Path: ...
