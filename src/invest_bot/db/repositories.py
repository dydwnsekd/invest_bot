from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from io import StringIO
from typing import Sequence

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from invest_bot.db.contracts import (
    DailyPriceRecord,
    DatasetFrameRecord,
    InvestorDailyRecord,
    StockInfoSnapshotRecord,
    ReportFavoriteSymbolRecord,
    StockRecord,
)
from invest_bot.db.models import DatasetFrame, DailyPrice, InvestorDaily, ReportFavoriteSymbol, StockInfoSnapshot, Symbol


class SqlAlchemyStockRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def upsert(self, record: StockRecord) -> None:
        with self.session_factory() as session:
            self._upsert_with_session(session, record)
            session.commit()

    def get_by_symbol(self, symbol: str) -> StockRecord | None:
        normalized = normalize_symbol(symbol)
        with self.session_factory() as session:
            row = session.get(Symbol, normalized)
            if row is None:
                return None
            return StockRecord(symbol=row.symbol, symbol_name=row.symbol_name, market=row.market)

    def list_all(self) -> Sequence[StockRecord]:
        with self.session_factory() as session:
            rows = session.scalars(select(Symbol).order_by(Symbol.symbol)).all()
            return [StockRecord(symbol=row.symbol, symbol_name=row.symbol_name, market=row.market) for row in rows]

    @staticmethod
    def _upsert_with_session(session: Session, record: StockRecord) -> Symbol:
        normalized = normalize_symbol(record.symbol)
        existing = session.get(Symbol, normalized)
        if existing is None:
            existing = Symbol(
                symbol=normalized,
                symbol_name=record.symbol_name or normalized,
                market=record.market or "unknown",
            )
            session.add(existing)
            session.flush()
            return existing

        if record.symbol_name and (existing.symbol_name in {existing.symbol, "", "unknown"} or record.symbol_name != normalized):
            existing.symbol_name = record.symbol_name
        if record.market and (existing.market in {"", "unknown"} or record.market != "unknown"):
            existing.market = record.market
        session.flush()
        return existing


class SqlAlchemyDailyPriceRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def replace_for_symbol(self, symbol: str, records: Sequence[DailyPriceRecord]) -> None:
        normalized = normalize_symbol(symbol)
        with self.session_factory() as session:
            ensure_symbol(session, normalized)
            for record in records:
                existing = session.scalar(
                    select(DailyPrice).where(DailyPrice.symbol == normalized, DailyPrice.trade_date == record.trade_date)
                )
                if existing is None:
                    existing = DailyPrice(symbol=normalized, trade_date=record.trade_date)
                    session.add(existing)
                existing.open_price = to_decimal(record.open_price)
                existing.high_price = to_decimal(record.high_price)
                existing.low_price = to_decimal(record.low_price)
                existing.close_price = to_decimal(record.close_price)
                existing.volume = int(record.volume) if record.volume is not None else None
                existing.collected_at = record.collected_at
            session.commit()

    def list_for_symbol(self, symbol: str, limit: int | None = None) -> Sequence[DailyPriceRecord]:
        normalized = normalize_symbol(symbol)
        with self.session_factory() as session:
            stmt = select(DailyPrice).where(DailyPrice.symbol == normalized).order_by(DailyPrice.trade_date.desc())
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = session.scalars(stmt).all()
            return [
                DailyPriceRecord(
                    symbol=row.symbol,
                    trade_date=row.trade_date,
                    open_price=to_float(row.open_price),
                    high_price=to_float(row.high_price),
                    low_price=to_float(row.low_price),
                    close_price=to_float(row.close_price),
                    volume=float(row.volume) if row.volume is not None else None,
                    collected_at=row.collected_at,
                )
                for row in rows
            ]

    def latest_trade_date(self, symbol: str) -> date | None:
        normalized = normalize_symbol(symbol)
        with self.session_factory() as session:
            return session.scalar(select(func.max(DailyPrice.trade_date)).where(DailyPrice.symbol == normalized))


class SqlAlchemyStockInfoSnapshotRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def save(self, record: StockInfoSnapshotRecord) -> None:
        normalized = normalize_symbol(record.symbol)
        with self.session_factory() as session:
            ensure_symbol(session, normalized, symbol_name=record.product_name)
            session.add(
                StockInfoSnapshot(
                    symbol=normalized,
                    captured_at=record.captured_at,
                    product_name=record.product_name,
                    market_code=record.market_code,
                    raw_payload=record.raw_payload,
                )
            )
            session.commit()


class SqlAlchemyInvestorDailyRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def replace_for_symbol(self, symbol: str, records: Sequence[InvestorDailyRecord]) -> None:
        normalized = normalize_symbol(symbol)
        with self.session_factory() as session:
            ensure_symbol(session, normalized)
            for record in records:
                existing = session.scalar(
                    select(InvestorDaily).where(InvestorDaily.symbol == normalized, InvestorDaily.trade_date == record.trade_date)
                )
                if existing is None:
                    existing = InvestorDaily(symbol=normalized, trade_date=record.trade_date)
                    session.add(existing)
                existing.foreign_net_qty = to_decimal(record.foreign_net_qty)
                existing.institutional_net_qty = to_decimal(record.institutional_net_qty)
                existing.personal_net_qty = to_decimal(record.personal_net_qty)
                existing.raw_payload = record.raw_payload
                existing.collected_at = record.collected_at
            session.commit()

    def list_for_symbol(self, symbol: str, limit: int | None = None) -> Sequence[InvestorDailyRecord]:
        normalized = normalize_symbol(symbol)
        with self.session_factory() as session:
            stmt = select(InvestorDaily).where(InvestorDaily.symbol == normalized).order_by(InvestorDaily.trade_date.desc())
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = session.scalars(stmt).all()
            return [
                InvestorDailyRecord(
                    symbol=row.symbol,
                    trade_date=row.trade_date,
                    foreign_net_qty=to_float(row.foreign_net_qty),
                    institutional_net_qty=to_float(row.institutional_net_qty),
                    personal_net_qty=to_float(row.personal_net_qty),
                    raw_payload=row.raw_payload or "",
                    collected_at=row.collected_at,
                )
                for row in rows
            ]

    def latest_trade_date(self, symbol: str) -> date | None:
        normalized = normalize_symbol(symbol)
        with self.session_factory() as session:
            return session.scalar(select(func.max(InvestorDaily.trade_date)).where(InvestorDaily.symbol == normalized))


class SqlAlchemyDatasetFrameRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def save(self, record: DatasetFrameRecord) -> None:
        normalized = normalize_symbol(record.symbol) if record.symbol else None
        with self.session_factory() as session:
            if normalized:
                ensure_symbol(session, normalized)
            existing = session.scalar(
                select(DatasetFrame).where(
                    DatasetFrame.dataset == record.dataset,
                    DatasetFrame.filename == record.filename,
                )
            )
            if existing is None:
                existing = DatasetFrame(dataset=record.dataset, filename=record.filename)
                session.add(existing)
            existing.symbol = normalized
            existing.as_of_date = record.as_of_date
            existing.row_count = record.row_count
            existing.frame_json = record.frame_json
            existing.created_at = record.created_at
            existing.updated_at = datetime.now(UTC)
            session.commit()

    def load(self, dataset: str, filename: str) -> DatasetFrameRecord | None:
        with self.session_factory() as session:
            row = session.scalar(
                select(DatasetFrame).where(DatasetFrame.dataset == dataset, DatasetFrame.filename == filename)
            )
            if row is None:
                return None
            return DatasetFrameRecord(
                dataset=row.dataset,
                filename=row.filename,
                frame_json=row.frame_json,
                row_count=row.row_count,
                created_at=row.created_at,
                symbol=row.symbol or "",
                as_of_date=row.as_of_date,
            )

    def latest_for_symbol(self, dataset: str, symbol: str) -> DatasetFrameRecord | None:
        normalized = normalize_symbol(symbol)
        with self.session_factory() as session:
            row = session.scalar(
                select(DatasetFrame)
                .where(DatasetFrame.dataset == dataset, DatasetFrame.symbol == normalized)
                .order_by(DatasetFrame.as_of_date.desc(), DatasetFrame.created_at.desc(), DatasetFrame.id.desc())
                .limit(1)
            )
            if row is None:
                return None
            return DatasetFrameRecord(
                dataset=row.dataset,
                filename=row.filename,
                frame_json=row.frame_json,
                row_count=row.row_count,
                created_at=row.created_at,
                symbol=row.symbol or "",
                as_of_date=row.as_of_date,
            )

    def list_latest(self, datasets: Sequence[str]) -> Sequence[DatasetFrameRecord]:
        records: list[DatasetFrameRecord] = []
        with self.session_factory() as session:
            for dataset in datasets:
                rows = session.scalars(
                    select(DatasetFrame)
                    .where(DatasetFrame.dataset == dataset)
                    .order_by(DatasetFrame.as_of_date.desc(), DatasetFrame.created_at.desc(), DatasetFrame.id.desc())
                ).all()
                seen_symbols: set[str] = set()
                for row in rows:
                    key = row.symbol or row.filename
                    if key in seen_symbols:
                        continue
                    seen_symbols.add(key)
                    records.append(
                        DatasetFrameRecord(
                            dataset=row.dataset,
                            filename=row.filename,
                            frame_json=row.frame_json,
                            row_count=row.row_count,
                            created_at=row.created_at,
                            symbol=row.symbol or "",
                            as_of_date=row.as_of_date,
                        )
                    )
        return records


class SqlAlchemyReportFavoriteSymbolRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def load_all(self) -> Sequence[ReportFavoriteSymbolRecord]:
        with self.session_factory() as session:
            rows = session.scalars(select(ReportFavoriteSymbol).order_by(ReportFavoriteSymbol.created_at.asc())).all()
            return [
                ReportFavoriteSymbolRecord(
                    symbol=row.symbol,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                for row in rows
            ]

    def add(self, symbol: str) -> bool:
        normalized = normalize_symbol(symbol)
        if not normalized:
            return False
        with self.session_factory() as session:
            existing = session.get(ReportFavoriteSymbol, normalized)
            if existing is not None:
                return False
            try:
                session.add(ReportFavoriteSymbol(symbol=normalized))
                session.commit()
                return True
            except IntegrityError:
                session.rollback()
                return False

    def remove(self, symbol: str) -> bool:
        normalized = normalize_symbol(symbol)
        if not normalized:
            return False
        with self.session_factory() as session:
            existing = session.get(ReportFavoriteSymbol, normalized)
            if existing is None:
                return False
            session.delete(existing)
            session.commit()
            return True


def ensure_symbol(session: Session, symbol: str, *, symbol_name: str | None = None, market: str = "unknown") -> None:
    SqlAlchemyStockRepository._upsert_with_session(
        session,
        StockRecord(symbol=symbol, symbol_name=symbol_name or symbol, market=market),
    )


def normalize_symbol(value: object) -> str:
    text = str(value).strip()
    if text.isdigit():
        return text.zfill(6)
    return text


def to_decimal(value: float | int | str | Decimal | None) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def frame_to_json(frame: pd.DataFrame) -> str:
    return frame.to_json(orient="table", date_format="iso", force_ascii=False)


def frame_from_json(payload: str) -> pd.DataFrame:
    if not payload.strip():
        return pd.DataFrame()
    return pd.read_json(StringIO(payload), orient="table")
