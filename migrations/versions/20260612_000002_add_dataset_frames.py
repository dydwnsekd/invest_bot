"""add dataset frames

Revision ID: 20260612_000002
Revises: 20260606_000001
Create Date: 2026-06-12 22:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260612_000002"
down_revision = "20260606_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dataset_frames",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("symbol", sa.String(length=12), nullable=True),
        sa.Column("as_of_date", sa.Date(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("frame_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["symbol"], ["symbols.symbol"], name=op.f("fk_dataset_frames_symbol_symbols"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataset_frames")),
        sa.UniqueConstraint("dataset", "filename", name="uq_dataset_frames_dataset_filename"),
    )
    op.create_index(op.f("ix_dataset_frames_as_of_date"), "dataset_frames", ["as_of_date"], unique=False)
    op.create_index(op.f("ix_dataset_frames_dataset"), "dataset_frames", ["dataset"], unique=False)
    op.create_index(op.f("ix_dataset_frames_symbol"), "dataset_frames", ["symbol"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_dataset_frames_symbol"), table_name="dataset_frames")
    op.drop_index(op.f("ix_dataset_frames_dataset"), table_name="dataset_frames")
    op.drop_index(op.f("ix_dataset_frames_as_of_date"), table_name="dataset_frames")
    op.drop_table("dataset_frames")
