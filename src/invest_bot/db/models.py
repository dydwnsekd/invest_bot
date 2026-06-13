from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from invest_bot.db.metadata import Base


class Symbol(Base):
    __tablename__ = "symbols"

    symbol: Mapped[str] = mapped_column(String(12), primary_key=True)
    symbol_name: Mapped[str] = mapped_column(String(120), nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False
    )

    daily_price_rows: Mapped[list[DailyPrice]] = relationship(back_populates="symbol_ref", cascade="all, delete-orphan")
    stock_info_snapshots: Mapped[list[StockInfoSnapshot]] = relationship(
        back_populates="symbol_ref", cascade="all, delete-orphan"
    )
    investor_daily_rows: Mapped[list[InvestorDaily]] = relationship(
        back_populates="symbol_ref", cascade="all, delete-orphan"
    )


class DailyPrice(Base):
    __tablename__ = "daily_prices"
    __table_args__ = (UniqueConstraint("symbol", "trade_date", name="uq_daily_prices_symbol_trade_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("symbols.symbol", ondelete="CASCADE"), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    open_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    high_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    low_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    close_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    volume: Mapped[int | None] = mapped_column()
    turnover: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    source_filename: Mapped[str | None] = mapped_column(String(255))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    symbol_ref: Mapped[Symbol] = relationship(back_populates="daily_price_rows")


class StockInfoSnapshot(Base):
    __tablename__ = "stock_info_snapshots"
    __table_args__ = (UniqueConstraint("symbol", "captured_at", name="uq_stock_info_symbol_captured_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("symbols.symbol", ondelete="CASCADE"), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    product_name: Mapped[str | None] = mapped_column(String(120))
    market_code: Mapped[str | None] = mapped_column(String(32))
    raw_payload: Mapped[str | None] = mapped_column(Text)
    source_filename: Mapped[str | None] = mapped_column(String(255))

    symbol_ref: Mapped[Symbol] = relationship(back_populates="stock_info_snapshots")


class InvestorDaily(Base):
    __tablename__ = "investor_daily"
    __table_args__ = (UniqueConstraint("symbol", "trade_date", name="uq_investor_daily_symbol_trade_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("symbols.symbol", ondelete="CASCADE"), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    foreign_net_qty: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    institutional_net_qty: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    personal_net_qty: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    raw_payload: Mapped[str | None] = mapped_column(Text)
    source_filename: Mapped[str | None] = mapped_column(String(255))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    symbol_ref: Mapped[Symbol] = relationship(back_populates="investor_daily_rows")


class DatasetFrame(Base):
    __tablename__ = "dataset_frames"
    __table_args__ = (UniqueConstraint("dataset", "filename", name="uq_dataset_frames_dataset_filename"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    symbol: Mapped[str | None] = mapped_column(ForeignKey("symbols.symbol", ondelete="SET NULL"), index=True)
    as_of_date: Mapped[date | None] = mapped_column(Date, index=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    frame_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False
    )

    symbol_ref: Mapped[Symbol | None] = relationship()
