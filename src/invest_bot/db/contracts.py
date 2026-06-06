from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol, Sequence, runtime_checkable


@dataclass(frozen=True, slots=True)
class StockRecord:
    symbol: str
    symbol_name: str
    market: str


@dataclass(frozen=True, slots=True)
class DailyPriceRecord:
    symbol: str
    trade_date: date
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    collected_at: datetime


@dataclass(frozen=True, slots=True)
class InvestorDailyRecord:
    symbol: str
    trade_date: date
    investor_type: str
    net_volume: float
    net_amount: float
    collected_at: datetime


@dataclass(frozen=True, slots=True)
class MarketReportRecord:
    symbol: str
    trade_date: date
    summary: str
    created_at: datetime


@runtime_checkable
class StockRepository(Protocol):
    def upsert(self, record: StockRecord) -> None: ...

    def get_by_symbol(self, symbol: str) -> StockRecord | None: ...

    def list_all(self) -> Sequence[StockRecord]: ...


@runtime_checkable
class DailyPriceRepository(Protocol):
    def replace_for_symbol(self, symbol: str, records: Sequence[DailyPriceRecord]) -> None: ...

    def list_for_symbol(self, symbol: str, limit: int | None = None) -> Sequence[DailyPriceRecord]: ...


@runtime_checkable
class InvestorDailyRepository(Protocol):
    def replace_for_symbol(self, symbol: str, records: Sequence[InvestorDailyRecord]) -> None: ...

    def list_for_symbol(self, symbol: str, limit: int | None = None) -> Sequence[InvestorDailyRecord]: ...


@runtime_checkable
class MarketReportRepository(Protocol):
    def save(self, record: MarketReportRecord) -> None: ...

    def latest_for_symbol(self, symbol: str) -> MarketReportRecord | None: ...
