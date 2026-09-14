"""add report favorite symbols

Revision ID: 20260703_000003
Revises: 20260612_000002
Create Date: 2026-07-03 23:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260703_000003"
down_revision = "20260612_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_favorite_symbols",
        sa.Column("symbol", sa.String(length=12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("symbol", name=op.f("pk_report_favorite_symbols")),
    )


def downgrade() -> None:
    op.drop_table("report_favorite_symbols")
