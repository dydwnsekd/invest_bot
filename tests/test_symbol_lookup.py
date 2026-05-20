from __future__ import annotations

import pandas as pd
import pytest

from invest_bot.market.storage import CsvStorage
from invest_bot.market.symbol_lookup import SymbolLookup
from tests.helpers import make_test_dir


def test_symbol_lookup_resolves_code_directly():
    lookup = SymbolLookup(make_test_dir("symbol_lookup_empty") / "stock_info")

    resolved = lookup.resolve("005930")

    assert resolved.symbol == "005930"
    assert resolved.raw_input == "005930"


def test_symbol_lookup_resolves_exact_name_from_stock_info():
    test_dir = make_test_dir("symbol_lookup_exact")
    storage = CsvStorage(test_dir / "raw")
    storage.save("stock_info", "005930.csv", pd.DataFrame([{"pdno": "005930", "prdt_abrv_name": "삼성전자"}]))

    lookup = SymbolLookup(test_dir / "raw" / "stock_info")
    resolved = lookup.resolve("삼성전자")

    assert resolved.symbol == "005930"
    assert resolved.symbol_name == "삼성전자"


def test_symbol_lookup_resolves_unique_partial_name():
    test_dir = make_test_dir("symbol_lookup_partial")
    storage = CsvStorage(test_dir / "raw")
    storage.save("stock_info", "005930.csv", pd.DataFrame([{"pdno": "005930", "prdt_abrv_name": "삼성전자"}]))
    storage.save("stock_info", "000660.csv", pd.DataFrame([{"pdno": "000660", "prdt_abrv_name": "SK하이닉스"}]))

    lookup = SymbolLookup(test_dir / "raw" / "stock_info")
    resolved = lookup.resolve("하이닉스")

    assert resolved.symbol == "000660"
    assert resolved.symbol_name == "SK하이닉스"


def test_symbol_lookup_raises_for_unknown_name():
    test_dir = make_test_dir("symbol_lookup_unknown")
    storage = CsvStorage(test_dir / "raw")
    storage.save("stock_info", "005930.csv", pd.DataFrame([{"pdno": "005930", "prdt_abrv_name": "삼성전자"}]))

    lookup = SymbolLookup(test_dir / "raw" / "stock_info")

    with pytest.raises(ValueError):
        lookup.resolve("없는종목")
