from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(slots=True)
class SavedDataset:
    dataset: str
    path: Path
    rows: int


class CsvStorage:
    """Persist collected datasets under the project's raw data directory."""

    def __init__(self, root_dir: str | Path = "data/raw/domestic_stock") -> None:
        self.root_dir = Path(root_dir)

    def save(self, dataset: str, filename: str, frame: pd.DataFrame) -> SavedDataset:
        dataset_dir = self.root_dir / dataset
        dataset_dir.mkdir(parents=True, exist_ok=True)
        file_path = dataset_dir / filename
        frame.to_csv(file_path, index=False, encoding="utf-8-sig")
        return SavedDataset(dataset=dataset, path=file_path, rows=len(frame))
