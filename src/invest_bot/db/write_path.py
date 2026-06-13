from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

import pandas as pd

from invest_bot.db.contracts import DailyPriceRecord, InvestorDailyRecord, StockInfoSnapshotRecord, StockRecord
from invest_bot.db.engine import build_engine, build_session_factory
from invest_bot.db.repositories import (
    SqlAlchemyDailyPriceRepository,
    SqlAlchemyInvestorDailyRepository,
    SqlAlchemyStockInfoSnapshotRepository,
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
        self.stock_info_repository = SqlAlchemyStockInfoSnapshotRepository(self.session_factory)
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
        normalized = normalize_symbol(symbol)
        if stock_info.empty:
            self.stock_repository.upsert(StockRecord(symbol=normalized, symbol_name=normalized, market=self.default_market))
            return
        first_row = stock_info.iloc[0].to_dict()
        product_name = str(first_row.get("prdt_abrv_name") or first_row.get("symbol_name") or normalized).strip()
        market_code = str(first_row.get("prdt_type_cd") or first_row.get("market_code") or self.default_market).strip()
        self.stock_repository.upsert(StockRecord(symbol=normalized, symbol_name=product_name, market=market_code))
        self.stock_info_repository.save(
            StockInfoSnapshotRecord(
                symbol=normalized,
                product_name=product_name,
                market_code=market_code,
                raw_payload=frame_payload(stock_info),
                captured_at=datetime.now(UTC),
            )
        )

    def save_investor_daily(
        self, symbol: str, target_date: date, investor_daily: pd.DataFrame, investor_summary: pd.DataFrame
    ) -> None:
        normalized = normalize_symbol(symbol)
        summary_row: dict[str, Any]
        if investor_summary.empty:
            summary_row = {"trade_date": target_date.isoformat()}
        else:
            summary_row = investor_summary.iloc[0].to_dict()
        trade_date = parse_trade_date(summary_row.get("trade_date") or summary_row.get("stck_bsop_date")) or target_date
        self.stock_repository.upsert(StockRecord(symbol=normalized, symbol_name=normalized, market=self.default_market))
        self.investor_daily_repository.replace_for_symbol(
            normalized,
            [
                InvestorDailyRecord(
                    symbol=normalized,
                    trade_date=trade_date,
                    foreign_net_qty=parse_number(summary_row.get("foreign_net_qty") or summary_row.get("frgn_ntby_qty")),
                    institutional_net_qty=parse_number(
                        summary_row.get("institutional_net_qty") or summary_row.get("orgn_ntby_qty")
                    ),
                    personal_net_qty=parse_number(summary_row.get("personal_net_qty") or summary_row.get("prsn_ntby_qty")),
                    raw_payload=frame_payload(investor_daily),
                    collected_at=datetime.now(UTC),
                )
            ],
        )


def frame_payload(frame: pd.DataFrame) -> str:
    return json.dumps(frame.to_dict(orient="records"), ensure_ascii=False, default=str)


def parse_trade_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        return datetime.strptime(text, "%Y%m%d").date()
    return datetime.fromisoformat(text).date()


def parse_number(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    return float(text)
