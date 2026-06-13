from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from invest_bot.config.settings import AppSettings
from invest_bot.market.collector import MarketDataCollector
from invest_bot.market.storage import SavedDataset
from invest_bot.market.symbol_lookup import SymbolLookup
from tests.helpers import make_test_dir


@dataclass
class InMemoryStorage:
    root_dir: Path
    saved: list[SavedDataset]
    frames: dict[tuple[str, str], pd.DataFrame] | None = None

    def __post_init__(self) -> None:
        if self.frames is None:
            self.frames = {}

    def save(self, dataset: str, filename: str, frame: pd.DataFrame) -> SavedDataset:
        path = self.root_dir / dataset / filename
        result = SavedDataset(dataset=dataset, path=path, rows=len(frame))
        self.saved.append(result)
        self.frames[(dataset, filename)] = frame.copy()
        return result

    def load(self, dataset: str, filename: str) -> pd.DataFrame:
        return self.frames[(dataset, filename)].copy()

    def latest_filename(self, dataset: str, symbol: str) -> str | None:
        matches = [
            filename
            for stored_dataset, filename in self.frames
            if stored_dataset == dataset and (not symbol or filename.startswith(symbol))
        ]
        return matches[-1] if matches else None


class InMemoryStockMasterRepository:
    def __init__(self, entries: list[dict[str, str]] | None = None) -> None:
        self.entries = entries or []
        self.refresh_calls = 0

    def load_entries(self) -> list[dict[str, str]]:
        return list(self.entries)

    def ensure_updated(self, force: bool = False) -> Path:
        if force:
            self.refresh_calls += 1
        return Path("memory://stock-master.csv")


def test_market_data_collector_accepts_storage_protocol():
    storage = InMemoryStorage(root_dir=Path("memory://raw"), saved=[])
    collector = MarketDataCollector(settings=AppSettings(), storage=storage)

    result = collector.save_stock_info("005930", pd.DataFrame([{"pdno": "005930"}]))

    assert result.dataset == "stock_info"
    assert result.rows == 1
    assert len(storage.saved) == 1


def test_symbol_lookup_accepts_repository_protocol_without_concrete_subclass():
    test_dir = make_test_dir("symbol_lookup_protocol")
    repo = InMemoryStockMasterRepository(entries=[{"symbol": "005930", "symbol_name": "삼성전자"}])
    lookup = SymbolLookup(test_dir / "stock_info", master_repository=repo)

    resolved = lookup.resolve("삼성전자")

    assert resolved.symbol == "005930"
    assert repo.refresh_calls == 0
