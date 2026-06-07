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
    open_price: float | None
    high_price: float | None
    low_price: float | None
    close_price: float | None
    volume: float | None
    collected_at: datetime


@dataclass(frozen=True, slots=True)
class StockInfoSnapshotRecord:
    symbol: str
    product_name: str
    market_code: str
    raw_payload: str
    captured_at: datetime


@dataclass(frozen=True, slots=True)
class InvestorDailyRecord:
    symbol: str
    trade_date: date
    foreign_net_qty: float | None
    institutional_net_qty: float | None
    personal_net_qty: float | None
    raw_payload: str
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

    def latest_trade_date(self, symbol: str) -> date | None: ...


@runtime_checkable
class StockInfoSnapshotRepository(Protocol):
    def save(self, record: StockInfoSnapshotRecord) -> None: ...


@runtime_checkable
class InvestorDailyRepository(Protocol):
    def replace_for_symbol(self, symbol: str, records: Sequence[InvestorDailyRecord]) -> None: ...

    def list_for_symbol(self, symbol: str, limit: int | None = None) -> Sequence[InvestorDailyRecord]: ...

    def latest_trade_date(self, symbol: str) -> date | None: ...


@runtime_checkable
class MarketReportRepository(Protocol):
    def save(self, record: MarketReportRecord) -> None: ...

    def latest_for_symbol(self, symbol: str) -> MarketReportRecord | None: ...
