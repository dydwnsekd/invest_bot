from __future__ import annotations

import pandas as pd
import pytest

from invest_bot.market.storage import CsvStorage
from invest_bot.market.stock_master import StockMasterRepository
from invest_bot.market.symbol_lookup import SymbolLookup
from tests.helpers import make_test_dir


class StubStockMasterRepository(StockMasterRepository):
    def __init__(self, master_file, refresh_entries=None):
        super().__init__(master_file)
        self.refresh_entries = refresh_entries or []
        self.refresh_calls = 0

    def ensure_updated(self, force: bool = False):
        if force:
            self.refresh_calls += 1
            self.write_entries(self.refresh_entries)
        elif not self.master_file.exists():
            self.write_entries([])
        return self.master_file


def test_symbol_lookup_resolves_code_directly():
    test_dir = make_test_dir("symbol_lookup_code")
    repo = StubStockMasterRepository(test_dir / "stock_master.csv")
    lookup = SymbolLookup(test_dir / "stock_info", master_repository=repo)

    resolved = lookup.resolve("005930")

    assert resolved.symbol == "005930"
    assert resolved.raw_input == "005930"


def test_symbol_lookup_resolves_exact_name_from_master_file():
    test_dir = make_test_dir("symbol_lookup_master_exact")
    repo = StubStockMasterRepository(test_dir / "stock_master.csv")
    repo.write_entries([{"symbol": "005930", "symbol_name": "삼성전자", "market": "KOSPI"}])
    lookup = SymbolLookup(test_dir / "stock_info", master_repository=repo)

    resolved = lookup.resolve("삼성전자")

    assert resolved.symbol == "005930"
    assert resolved.symbol_name == "삼성전자"


def test_symbol_lookup_resolves_unique_partial_name():
    test_dir = make_test_dir("symbol_lookup_partial")
    repo = StubStockMasterRepository(test_dir / "stock_master.csv")
    repo.write_entries(
        [
            {"symbol": "005930", "symbol_name": "삼성전자", "market": "KOSPI"},
            {"symbol": "000660", "symbol_name": "SK하이닉스", "market": "KOSPI"},
        ]
    )
    lookup = SymbolLookup(test_dir / "stock_info", master_repository=repo)

    resolved = lookup.resolve("하이닉스")

    assert resolved.symbol == "000660"
    assert resolved.symbol_name == "SK하이닉스"


def test_symbol_lookup_refreshes_master_when_name_is_missing():
    test_dir = make_test_dir("symbol_lookup_refresh")
    repo = StubStockMasterRepository(
        test_dir / "stock_master.csv",
        refresh_entries=[{"symbol": "035420", "symbol_name": "NAVER", "market": "KOSPI"}],
    )
    lookup = SymbolLookup(test_dir / "stock_info", master_repository=repo)

    resolved = lookup.resolve("NAVER")

    assert resolved.symbol == "035420"
    assert repo.refresh_calls == 1


def test_symbol_lookup_can_fallback_to_stock_info_entries():
    test_dir = make_test_dir("symbol_lookup_stock_info")
    storage = CsvStorage(test_dir / "raw")
    storage.save("stock_info", "005930.csv", pd.DataFrame([{"pdno": "005930", "prdt_abrv_name": "삼성전자"}]))
    repo = StubStockMasterRepository(test_dir / "stock_master.csv")
    lookup = SymbolLookup(test_dir / "raw" / "stock_info", master_repository=repo)

    resolved = lookup.resolve("삼성전자")

    assert resolved.symbol == "005930"
    assert resolved.symbol_name == "삼성전자"


def test_symbol_lookup_raises_for_unknown_name():
    test_dir = make_test_dir("symbol_lookup_unknown")
    repo = StubStockMasterRepository(test_dir / "stock_master.csv")
    repo.write_entries([{"symbol": "005930", "symbol_name": "삼성전자", "market": "KOSPI"}])
    lookup = SymbolLookup(test_dir / "stock_info", master_repository=repo)

    with pytest.raises(ValueError):
        lookup.resolve("없는종목")
