from __future__ import annotations

import json
from datetime import UTC, date, datetime
from math import isfinite
from typing import Any

import pandas as pd

from invest_bot.db.contracts import DailyPriceRecord, InvestorDailyRecord, StockRecord
from invest_bot.db.engine import build_engine, build_session_factory
from invest_bot.db.repositories import (
    SqlAlchemyDailyPriceRepository,
    SqlAlchemyInvestorDailyRepository,
    SqlAlchemyStockRepository,
    normalize_symbol,
)


class SqlAlchemyMarketDataWriter:
    def __init__(self, database_url: str, *, default_market: str = "domestic_stock") -> None:
        self.engine = build_engine(database_url)
        self.session_factory = build_session_factory(self.engine)
        self.default_market = default_market
        self.stock_repository = SqlAlchemyStockRepository(self.session_factory)
        self.daily_price_repository = SqlAlchemyDailyPriceRepository(self.session_factory)
        self.investor_daily_repository = SqlAlchemyInvestorDailyRepository(self.session_factory)

    def save_daily_prices(
        self, symbol: str, start_date: date, end_date: date, summary: pd.DataFrame, prices: pd.DataFrame
    ) -> None:
        normalized = normalize_symbol(symbol)
        self.stock_repository.upsert(StockRecord(symbol=normalized, symbol_name=normalized, market=self.default_market))
        records: list[DailyPriceRecord] = []
        for row in prices.to_dict(orient="records"):
            trade_date = parse_trade_date(row.get("trade_date") or row.get("stck_bsop_date"))
            if trade_date is None:
                continue
            records.append(
                DailyPriceRecord(
                    symbol=normalized,
                    trade_date=trade_date,
                    open_price=parse_number(row.get("open_price") or row.get("stck_oprc")),
                    high_price=parse_number(row.get("high_price") or row.get("stck_hgpr")),
                    low_price=parse_number(row.get("low_price") or row.get("stck_lwpr")),
                    close_price=parse_number(row.get("close_price") or row.get("stck_clpr")),
                    volume=parse_number(row.get("volume") or row.get("acml_vol")),
                    collected_at=datetime.now(UTC),
                )
            )
        if records:
            self.daily_price_repository.replace_for_symbol(normalized, records)

    def save_stock_info(self, symbol: str, stock_info: pd.DataFrame) -> None:
        _ = (symbol, stock_info)
        return None

    def save_investor_daily(
        self, symbol: str, target_date: date, investor_daily: pd.DataFrame, investor_summary: pd.DataFrame
    ) -> None:
        normalized = normalize_symbol(symbol)
        records: list[InvestorDailyRecord] = []
        collected_at = datetime.now(UTC)
        raw_payload = frame_payload(investor_daily)
        for summary_row in investor_summary.to_dict(orient="records"):
            trade_date = parse_trade_date(first_value(summary_row, "trade_date", "stck_bsop_date"))
            if trade_date is None:
                continue
            foreign_net_qty = parse_number(first_value(summary_row, "foreign_net_qty", "frgn_ntby_qty"))
            institutional_net_qty = parse_number(first_value(summary_row, "institutional_net_qty", "orgn_ntby_qty"))
            personal_net_qty = parse_number(first_value(summary_row, "personal_net_qty", "prsn_ntby_qty"))
            if foreign_net_qty is None and institutional_net_qty is None and personal_net_qty is None:
                continue
            records.append(
                InvestorDailyRecord(
                    symbol=normalized,
                    trade_date=trade_date,
                    foreign_net_qty=foreign_net_qty,
                    institutional_net_qty=institutional_net_qty,
                    personal_net_qty=personal_net_qty,
                    raw_payload=raw_payload,
                    collected_at=collected_at,
                )
            )
        if not records:
            return
        self.stock_repository.upsert(StockRecord(symbol=normalized, symbol_name=normalized, market=self.default_market))
        self.investor_daily_repository.replace_for_symbol(normalized, records)


def frame_payload(frame: pd.DataFrame) -> str:
    return json.dumps(frame.to_dict(orient="records"), ensure_ascii=False, default=str)


def parse_trade_date(value: Any) -> date | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if len(text) == 8 and text.isdigit():
            return datetime.strptime(text, "%Y%m%d").date()
        return datetime.fromisoformat(text).date()
    except (TypeError, ValueError):
        return None


def parse_number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).replace(",", "").strip()
    if text in {"", "-"}:
        return None
    try:
        parsed = float(text)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if isfinite(parsed) else None


def first_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is None or pd.isna(value):
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None
