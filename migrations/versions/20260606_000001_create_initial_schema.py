"""create initial schema

Revision ID: 20260606_000001
Revises:
Create Date: 2026-06-06 19:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260606_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "symbols",
        sa.Column("symbol", sa.String(length=12), nullable=False),
        sa.Column("symbol_name", sa.String(length=120), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("symbol", name=op.f("pk_symbols")),
    )

    op.create_table(
        "daily_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=12), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open_price", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("high_price", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("low_price", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("close_price", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("volume", sa.Integer(), nullable=True),
        sa.Column("turnover", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["symbol"], ["symbols.symbol"], name=op.f("fk_daily_prices_symbol_symbols"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_prices")),
        sa.UniqueConstraint("symbol", "trade_date", name="uq_daily_prices_symbol_trade_date"),
    )
    op.create_index(op.f("ix_daily_prices_symbol"), "daily_prices", ["symbol"], unique=False)
    op.create_index(op.f("ix_daily_prices_trade_date"), "daily_prices", ["trade_date"], unique=False)

    op.create_table(
        "stock_info_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=12), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("product_name", sa.String(length=120), nullable=True),
        sa.Column("market_code", sa.String(length=32), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["symbol"], ["symbols.symbol"], name=op.f("fk_stock_info_snapshots_symbol_symbols"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_info_snapshots")),
        sa.UniqueConstraint("symbol", "captured_at", name="uq_stock_info_symbol_captured_at"),
    )
    op.create_index(op.f("ix_stock_info_snapshots_symbol"), "stock_info_snapshots", ["symbol"], unique=False)

    op.create_table(
        "investor_daily",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=12), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("foreign_net_qty", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("institutional_net_qty", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("personal_net_qty", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["symbol"], ["symbols.symbol"], name=op.f("fk_investor_daily_symbol_symbols"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_investor_daily")),
        sa.UniqueConstraint("symbol", "trade_date", name="uq_investor_daily_symbol_trade_date"),
    )
    op.create_index(op.f("ix_investor_daily_symbol"), "investor_daily", ["symbol"], unique=False)
    op.create_index(op.f("ix_investor_daily_trade_date"), "investor_daily", ["trade_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_investor_daily_trade_date"), table_name="investor_daily")
    op.drop_index(op.f("ix_investor_daily_symbol"), table_name="investor_daily")
    op.drop_table("investor_daily")
    op.drop_index(op.f("ix_stock_info_snapshots_symbol"), table_name="stock_info_snapshots")
    op.drop_table("stock_info_snapshots")
    op.drop_index(op.f("ix_daily_prices_trade_date"), table_name="daily_prices")
    op.drop_index(op.f("ix_daily_prices_symbol"), table_name="daily_prices")
    op.drop_table("daily_prices")
    op.drop_table("symbols")
