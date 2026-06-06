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
from invest_bot.market.repositories import DatasetStorage
from invest_bot.market.storage import CsvStorage, SavedDataset


@dataclass(slots=True)
class CollectionRequest:
    symbol: str
    timeframe: str = "1d"
    limit: int = 100


@dataclass(slots=True)
class BatchCollectionResult:
    symbol: str
    status: str
    daily_summary_rows: int
    daily_price_rows: int
    stock_info_rows: int
    investor_daily_rows: int
    investor_summary_rows: int
    saved_files: list[str]
    error: str = ""


class MarketDataCollector:
    """Facade for the currently supported domestic stock collection flows."""

    def __init__(self, settings: AppSettings, storage: DatasetStorage | None = None) -> None:
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

    def collect_symbol_bundle(self, symbol: str, start_date: date, end_date: date) -> BatchCollectionResult:
        try:
            daily_summary, daily_prices = self.collect_daily_prices(symbol, start_date, end_date)
            stock_info = self.collect_stock_info(symbol)
            investor_daily, investor_summary = self.collect_investor_daily(symbol, end_date)

            saved_daily_summary, saved_daily_prices = self.save_daily_prices(
                symbol, start_date, end_date, daily_summary, daily_prices
            )
            saved_stock_info = self.save_stock_info(symbol, stock_info)
            saved_investor_detail, saved_investor_summary = self.save_investor_daily(
                symbol, end_date, investor_daily, investor_summary
            )

            return BatchCollectionResult(
                symbol=symbol,
                status="success",
                daily_summary_rows=len(daily_summary),
                daily_price_rows=len(daily_prices),
                stock_info_rows=len(stock_info),
                investor_daily_rows=len(investor_daily),
                investor_summary_rows=len(investor_summary),
                saved_files=[
                    str(saved_daily_summary.path),
                    str(saved_daily_prices.path),
                    str(saved_stock_info.path),
                    str(saved_investor_detail.path),
                    str(saved_investor_summary.path),
                ],
            )
        except Exception as error:  # noqa: BLE001
            return BatchCollectionResult(
                symbol=symbol,
                status="failed",
                daily_summary_rows=0,
                daily_price_rows=0,
                stock_info_rows=0,
                investor_daily_rows=0,
                investor_summary_rows=0,
                saved_files=[],
                error=str(error),
            )

    def collect_symbols_batch(self, symbols: list[str], start_date: date, end_date: date) -> list[BatchCollectionResult]:
        return [self.collect_symbol_bundle(symbol=symbol, start_date=start_date, end_date=end_date) for symbol in symbols]
