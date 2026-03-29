from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from invest_bot.clients.kis_client import KISClient
from invest_bot.config.settings import AppSettings
from invest_bot.market.domestic_stock import (
    DailyPriceRequest,
    DomesticStockDataCollector,
    InvestorDailyRequest,
    StockInfoRequest,
)
from invest_bot.market.storage import CsvStorage, SavedDataset


@dataclass(slots=True)
class CollectionRequest:
    symbol: str
    timeframe: str = "1d"
    limit: int = 100


class MarketDataCollector:
    """Facade for the currently supported domestic stock collection flows."""

    def __init__(self, settings: AppSettings, storage: CsvStorage | None = None) -> None:
        self.settings = settings
        self.collector = DomesticStockDataCollector(KISClient(settings=settings))
        self.storage = storage or CsvStorage()

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

    def save_daily_prices(
        self, symbol: str, start_date: date, end_date: date, summary: pd.DataFrame, prices: pd.DataFrame
    ) -> tuple[SavedDataset, SavedDataset]:
        date_range = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        summary_result = self.storage.save(
            dataset="daily_prices_summary",
            filename=f"{symbol}_{date_range}.csv",
            frame=summary,
        )
        prices_result = self.storage.save(
            dataset="daily_prices",
            filename=f"{symbol}_{date_range}.csv",
            frame=prices,
        )
        return summary_result, prices_result

    def save_stock_info(self, symbol: str, stock_info: pd.DataFrame) -> SavedDataset:
        return self.storage.save(
            dataset="stock_info",
            filename=f"{symbol}.csv",
            frame=stock_info,
        )

    def save_investor_daily(
        self, symbol: str, target_date: date, investor_daily: pd.DataFrame, investor_summary: pd.DataFrame
    ) -> tuple[SavedDataset, SavedDataset]:
        file_suffix = target_date.strftime("%Y%m%d")
        detail_result = self.storage.save(
            dataset="investor_daily",
            filename=f"{symbol}_{file_suffix}.csv",
            frame=investor_daily,
        )
        summary_result = self.storage.save(
            dataset="investor_daily_summary",
            filename=f"{symbol}_{file_suffix}.csv",
            frame=investor_summary,
        )
        return detail_result, summary_result
