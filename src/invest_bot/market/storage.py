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
        base_dir = Path(root_dir)
        if base_dir.is_absolute():
            self.root_dir = base_dir
        else:
            project_root = Path(__file__).resolve().parents[3]
            self.root_dir = project_root / base_dir

    def save(self, dataset: str, filename: str, frame: pd.DataFrame) -> SavedDataset:
        dataset_dir = self.root_dir / dataset
        dataset_dir.mkdir(parents=True, exist_ok=True)
        file_path = dataset_dir / filename
        frame.to_csv(file_path, index=False, encoding="utf-8-sig")
        return SavedDataset(dataset=dataset, path=file_path, rows=len(frame))

    def load(self, dataset: str, filename: str) -> pd.DataFrame:
        return pd.read_csv(self.root_dir / dataset / filename)

    def latest_filename(self, dataset: str, symbol: str) -> str | None:
        dataset_dir = self.root_dir / dataset
        if not dataset_dir.exists():
            return None
        matches = sorted(dataset_dir.glob(f"{symbol}_*.csv"), key=lambda path: path.stat().st_mtime, reverse=True)
        if not matches and dataset == "stock_info":
            exact_file = dataset_dir / f"{symbol}.csv"
            if exact_file.exists():
                return exact_file.name
        return matches[0].name if matches else None
