from __future__ import annotations

from datetime import date, datetime
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

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
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    symbol_ref: Mapped[Symbol] = relationship(back_populates="daily_price_rows")


class StockInfoSnapshot(Base):
    __tablename__ = "stock_info_snapshots"
    __table_args__ = (UniqueConstraint("symbol", "captured_at", name="uq_stock_info_symbol_captured_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("symbols.symbol", ondelete="CASCADE"), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    listed_shares: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    par_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    settlement_month: Mapped[str | None] = mapped_column(String(16))
    raw_payload: Mapped[str | None] = mapped_column(Text)
    source_filename: Mapped[str | None] = mapped_column(String(255))

    symbol_ref: Mapped[Symbol] = relationship(back_populates="stock_info_snapshots")


class InvestorDaily(Base):
    __tablename__ = "investor_daily"
    __table_args__ = (UniqueConstraint("symbol", "trade_date", name="uq_investor_daily_symbol_trade_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("symbols.symbol", ondelete="CASCADE"), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    investor_name: Mapped[str] = mapped_column(String(120), nullable=False)
    buy_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    sell_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    source_filename: Mapped[str | None] = mapped_column(String(255))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    symbol_ref: Mapped[Symbol] = relationship(back_populates="investor_daily_rows")
