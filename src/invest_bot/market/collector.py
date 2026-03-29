from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from invest_bot.clients.kis_client import KISClient
from invest_bot.config.settings import AppSettings
from invest_bot.market.domestic_stock import (
    DailyPriceRequest,
    DomesticStockDataCollector,
    InvestorDailyRequest,
    StockInfoRequest,
)


@dataclass(slots=True)
class CollectionRequest:
    symbol: str
    timeframe: str = "1d"
    limit: int = 100


class MarketDataCollector:
    """Facade for the currently supported domestic stock collection flows."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.collector = DomesticStockDataCollector(KISClient(settings=settings))

    def collect(self, request: CollectionRequest) -> dict[str, str | int]:
        return {"symbol": request.symbol, "timeframe": request.timeframe, "limit": request.limit, "status": "ready"}

    def collect_daily_prices(self, symbol: str, start_date: date, end_date: date) -> tuple[pd.DataFrame, pd.DataFrame]:
        return self.collector.collect_daily_prices(
            DailyPriceRequest(symbol=symbol, start_date=start_date, end_date=end_date)
        )

    def collect_stock_info(self, symbol: str) -> pd.DataFrame:
        return self.collector.collect_stock_info(StockInfoRequest(symbol=symbol))

    def collect_investor_daily(self, symbol: str, target_date: date) -> tuple[pd.DataFrame, pd.DataFrame]:
        return self.collector.collect_investor_daily(
            InvestorDailyRequest(symbol=symbol, target_date=target_date)
        )
