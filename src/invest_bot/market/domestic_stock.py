from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from invest_bot.clients.kis_client import KISClient


@dataclass(slots=True)
class DailyPriceRequest:
    symbol: str
    start_date: date
    end_date: date
    market_code: str = "J"
    period_code: str = "D"
    adjusted_price: bool = True


@dataclass(slots=True)
class StockInfoRequest:
    symbol: str
    product_type_code: str = "300"


@dataclass(slots=True)
class InvestorDailyRequest:
    symbol: str
    target_date: date
    market_code: str = "J"
    adjusted_price: bool = True
    extra_class_code: str = ""


class DomesticStockDataCollector:
    """Collect domestic stock datasets needed for strategy research."""

    def __init__(self, client: KISClient) -> None:
        self.client = client

    def collect_daily_prices(self, request: DailyPriceRequest) -> tuple[pd.DataFrame, pd.DataFrame]:
        payload = self.client.get_json(
            api_path="/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            tr_id="FHKST03010100",
            params={
                "FID_COND_MRKT_DIV_CODE": request.market_code,
                "FID_INPUT_ISCD": request.symbol,
                "FID_INPUT_DATE_1": request.start_date.strftime("%Y%m%d"),
                "FID_INPUT_DATE_2": request.end_date.strftime("%Y%m%d"),
                "FID_PERIOD_DIV_CODE": request.period_code,
                "FID_ORG_ADJ_PRC": "0" if request.adjusted_price else "1",
            },
        )
        summary = self._to_frame(payload.get("output1"))
        prices = self._to_frame(payload.get("output2"))
        return summary, prices

    def collect_stock_info(self, request: StockInfoRequest) -> pd.DataFrame:
        payload = self.client.get_json(
            api_path="/uapi/domestic-stock/v1/quotations/search-stock-info",
            tr_id="CTPF1002R",
            params={
                "PRDT_TYPE_CD": request.product_type_code,
                "PDNO": request.symbol,
            },
        )
        return self._to_frame(payload.get("output"))

    def collect_investor_daily(self, request: InvestorDailyRequest) -> tuple[pd.DataFrame, pd.DataFrame]:
        payload = self.client.get_json(
            api_path="/uapi/domestic-stock/v1/quotations/investor-trade-by-stock-daily",
            tr_id="FHPTJ04160001",
            params={
                "FID_COND_MRKT_DIV_CODE": request.market_code,
                "FID_INPUT_ISCD": request.symbol,
                "FID_INPUT_DATE_1": request.target_date.strftime("%Y%m%d"),
                "FID_ORG_ADJ_PRC": "0" if request.adjusted_price else "1",
                "FID_ETC_CLS_CODE": request.extra_class_code,
            },
        )
        by_investor = self._to_frame(payload.get("output1"))
        summary = self._to_frame(payload.get("output2"))
        return by_investor, summary

    @staticmethod
    def _to_frame(payload: Any) -> pd.DataFrame:
        if payload is None:
            return pd.DataFrame()
        if isinstance(payload, list):
            return pd.DataFrame(payload)
        return pd.DataFrame([payload])
