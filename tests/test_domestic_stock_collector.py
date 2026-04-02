from __future__ import annotations

from datetime import date

import pandas as pd

from invest_bot.config.settings import AppSettings
from invest_bot.market.collector import MarketDataCollector
from invest_bot.market.domestic_stock import DailyPriceRequest, DomesticStockDataCollector, InvestorDailyRequest, StockInfoRequest
from invest_bot.market.storage import CsvStorage
from tests.helpers import make_test_dir


class StubClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get_json(self, api_path, tr_id, params, tr_cont=""):
        self.calls.append(
            {
                "api_path": api_path,
                "tr_id": tr_id,
                "params": params,
                "tr_cont": tr_cont,
            }
        )
        return self.payload


def test_collect_daily_prices_maps_reference_endpoint():
    client = StubClient({"output1": {"symbol": "005930"}, "output2": [{"stck_bsop_date": "20260327"}]})
    collector = DomesticStockDataCollector(client)

    summary, prices = collector.collect_daily_prices(
        DailyPriceRequest(symbol="005930", start_date=date(2026, 3, 1), end_date=date(2026, 3, 27))
    )

    assert client.calls[0]["api_path"].endswith("inquire-daily-itemchartprice")
    assert client.calls[0]["tr_id"] == "FHKST03010100"
    assert client.calls[0]["params"]["FID_INPUT_ISCD"] == "005930"
    assert not summary.empty
    assert not prices.empty


def test_collect_stock_info_maps_reference_endpoint():
    client = StubClient({"output": {"prdt_abrv_name": "삼성전자", "pdno": "005930"}})
    collector = DomesticStockDataCollector(client)

    result = collector.collect_stock_info(StockInfoRequest(symbol="005930"))

    assert client.calls[0]["api_path"].endswith("search-stock-info")
    assert client.calls[0]["tr_id"] == "CTPF1002R"
    assert result.iloc[0]["pdno"] == "005930"


def test_collect_investor_daily_maps_reference_endpoint():
    client = StubClient({"output1": [{"frgn_ntby_qty": "100"}], "output2": {"stck_bsop_date": "20260327"}})
    collector = DomesticStockDataCollector(client)

    detail, summary = collector.collect_investor_daily(
        InvestorDailyRequest(symbol="005930", target_date=date(2026, 3, 27))
    )

    assert client.calls[0]["api_path"].endswith("investor-trade-by-stock-daily")
    assert client.calls[0]["tr_id"] == "FHPTJ04160001"
    assert not detail.empty
    assert not summary.empty


def test_market_data_collector_saves_all_requested_csv_files():
    test_dir = make_test_dir("market_data_collector")
    collector = MarketDataCollector(settings=AppSettings(), storage=CsvStorage(test_dir))

    daily_summary, daily_prices = collector.save_daily_prices(
        "005930",
        date(2026, 3, 1),
        date(2026, 3, 29),
        pd.DataFrame([{"symbol": "005930"}]),
        pd.DataFrame([{"stck_bsop_date": "20260328"}]),
    )
    stock_info = collector.save_stock_info("005930", pd.DataFrame([{"pdno": "005930"}]))
    investor_detail, investor_summary = collector.save_investor_daily(
        "005930",
        date(2026, 3, 29),
        pd.DataFrame([{"frgn_ntby_qty": "100"}]),
        pd.DataFrame([{"stck_bsop_date": "20260329"}]),
    )

    assert daily_summary.path.exists()
    assert daily_prices.path.exists()
    assert stock_info.path.exists()
    assert investor_detail.path.exists()
    assert investor_summary.path.exists()
