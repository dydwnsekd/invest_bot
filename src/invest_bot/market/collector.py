from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import pandas as pd

from invest_bot.clients.kis_client import KISClient
from invest_bot.config.settings import AppSettings
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.db.write_path import SqlAlchemyMarketDataWriter
from invest_bot.market.domestic_stock import (
    DailyPriceRequest,
    DomesticStockDataCollector,
    InvestorDailyRequest,
    StockInfoRequest,
)
from invest_bot.market.repositories import DatasetStorage, MarketDataWriter
from invest_bot.market.storage import SavedDataset

MIN_REQUIRED_DAILY_PRICE_ROWS = 60


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

    def __init__(
        self,
        settings: AppSettings,
        storage: DatasetStorage | None = None,
        db_writer: MarketDataWriter | None = None,
    ) -> None:
        self.settings = settings
        self.collector = DomesticStockDataCollector(KISClient(settings=settings))
        self.storage = storage or DbFrameStorage.from_settings(settings)
        self.db_writer = db_writer or self._build_default_db_writer()

    def _build_default_db_writer(self) -> MarketDataWriter | None:
        if not self.settings.enable_db_write:
            return None
        return SqlAlchemyMarketDataWriter(self.settings.database_url, default_market=self.settings.market)

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
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        summary: pd.DataFrame,
        prices: pd.DataFrame,
        *,
        _on_saved: Callable[[SavedDataset], None] | None = None,
    ) -> tuple[SavedDataset, SavedDataset]:
        date_range = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        summary_result = self.storage.save(
            dataset="daily_prices_summary",
            filename=f"{symbol}_{date_range}.csv",
            frame=summary,
        )
        if _on_saved is not None:
            _on_saved(summary_result)
        prices_result = self.storage.save(
            dataset="daily_prices",
            filename=f"{symbol}_{date_range}.csv",
            frame=prices,
        )
        if _on_saved is not None:
            _on_saved(prices_result)
        if self.db_writer is not None:
            self.db_writer.save_daily_prices(symbol, start_date, end_date, summary, prices)
        return summary_result, prices_result

    def save_stock_info(
        self,
        symbol: str,
        stock_info: pd.DataFrame,
        *,
        _on_saved: Callable[[SavedDataset], None] | None = None,
    ) -> SavedDataset:
        if not self._should_persist_stock_info(symbol, stock_info):
            return SavedDataset(
                dataset="stock_info",
                path=self.storage.root_dir / "stock_info" / f"{symbol}.csv",
                rows=len(stock_info),
            )
        result = self.storage.save(
            dataset="stock_info",
            filename=f"{symbol}.csv",
            frame=stock_info,
        )
        if _on_saved is not None:
            _on_saved(result)
        if self.db_writer is not None:
            self.db_writer.save_stock_info(symbol, stock_info)
        return result

    def save_investor_daily(
        self,
        symbol: str,
        target_date: date,
        investor_daily: pd.DataFrame,
        investor_summary: pd.DataFrame,
        *,
        _on_saved: Callable[[SavedDataset], None] | None = None,
    ) -> tuple[SavedDataset, SavedDataset]:
        file_suffix = target_date.strftime("%Y%m%d")
        detail_result = self.storage.save(
            dataset="investor_daily",
            filename=f"{symbol}_{file_suffix}.csv",
            frame=investor_daily,
        )
        if _on_saved is not None:
            _on_saved(detail_result)
        summary_result = self.storage.save(
            dataset="investor_daily_summary",
            filename=f"{symbol}_{file_suffix}.csv",
            frame=investor_summary,
        )
        if _on_saved is not None:
            _on_saved(summary_result)
        if self.db_writer is not None:
            self.db_writer.save_investor_daily(symbol, target_date, investor_daily, investor_summary)
        return detail_result, summary_result

    def collect_symbol_bundle(self, symbol: str, start_date: date, end_date: date) -> BatchCollectionResult:
        daily_summary_rows = 0
        daily_price_rows = 0
        stock_info_rows = 0
        investor_daily_rows = 0
        investor_summary_rows = 0
        saved_files: list[str] = []

        def record_saved(result: SavedDataset) -> None:
            saved_files.append(str(result.path))

        try:
            daily_summary, daily_prices = self.collect_daily_prices(symbol, start_date, end_date)
            daily_summary_rows = len(daily_summary)
            daily_price_rows = len(daily_prices)
            if len(daily_prices.index) < MIN_REQUIRED_DAILY_PRICE_ROWS:
                return BatchCollectionResult(
                    symbol=symbol,
                    status="failed",
                    daily_summary_rows=daily_summary_rows,
                    daily_price_rows=daily_price_rows,
                    stock_info_rows=0,
                    investor_daily_rows=0,
                    investor_summary_rows=0,
                    saved_files=[],
                    error=(
                        "At least "
                        f"{MIN_REQUIRED_DAILY_PRICE_ROWS} daily price rows are required for the current strategy analysis."
                    ),
                )
            stock_info_error = ""
            try:
                stock_info = self.collect_stock_info(symbol)
            except Exception as error:  # noqa: BLE001
                stock_info = self._fallback_stock_info(symbol, error)
                stock_info_error = str(error)
            stock_info_rows = len(stock_info)
            investor_daily, investor_summary = self.collect_investor_daily(symbol, end_date)
            investor_daily_rows = len(investor_daily)
            investor_summary_rows = len(investor_summary)
            persist_stock_info = self._should_persist_stock_info(symbol, stock_info)

            self.save_daily_prices(
                symbol, start_date, end_date, daily_summary, daily_prices, _on_saved=record_saved
            )
            if persist_stock_info:
                self.save_stock_info(symbol, stock_info, _on_saved=record_saved)
            self.save_investor_daily(
                symbol, end_date, investor_daily, investor_summary, _on_saved=record_saved
            )

            return BatchCollectionResult(
                symbol=symbol,
                status="success",
                daily_summary_rows=daily_summary_rows,
                daily_price_rows=daily_price_rows,
                stock_info_rows=stock_info_rows,
                investor_daily_rows=investor_daily_rows,
                investor_summary_rows=investor_summary_rows,
                saved_files=saved_files,
                error=stock_info_error,
            )
        except Exception as error:  # noqa: BLE001
            return BatchCollectionResult(
                symbol=symbol,
                status="failed",
                daily_summary_rows=daily_summary_rows,
                daily_price_rows=daily_price_rows,
                stock_info_rows=stock_info_rows,
                investor_daily_rows=investor_daily_rows,
                investor_summary_rows=investor_summary_rows,
                saved_files=saved_files,
                error=str(error),
            )

    def collect_symbols_batch(self, symbols: list[str], start_date: date, end_date: date) -> list[BatchCollectionResult]:
        return [self.collect_symbol_bundle(symbol=symbol, start_date=start_date, end_date=end_date) for symbol in symbols]

    @staticmethod
    def _fallback_stock_info(symbol: str, error: Exception) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "pdno": symbol,
                    "prdt_abrv_name": symbol,
                    "prdt_type_cd": "",
                    "collection_warning": str(error),
                }
            ]
        )

    @staticmethod
    def _should_persist_stock_info(symbol: str, stock_info: pd.DataFrame) -> bool:
        if stock_info.empty:
            return False
        first_row = stock_info.iloc[0]
        if str(first_row.get("collection_warning", "")).strip():
            return False
        symbol_name = str(first_row.get("prdt_abrv_name", "")).strip()
        product_code = str(first_row.get("pdno", "")).strip() or symbol
        normalized_symbol = str(product_code).strip().zfill(6) if str(product_code).strip().isdigit() else str(product_code).strip()
        normalized_name = str(symbol_name).strip().zfill(6) if str(symbol_name).strip().isdigit() else str(symbol_name).strip()
        return bool(symbol_name) and normalized_name != normalized_symbol
