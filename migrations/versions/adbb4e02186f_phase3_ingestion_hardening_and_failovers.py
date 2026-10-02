"""phase3_ingestion_hardening_and_failovers

Revision ID: adbb4e02186f
Revises: ef40759b6eb4
Create Date: 2026-10-02 15:15:26.787660

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'adbb4e02186f'
down_revision: str | Sequence[str] | None = 'ef40759b6eb4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: add exchange_failovers table and data_mode column to ohlcv."""
    # 1. Create exchange_failovers table
    op.create_table(
        "exchange_failovers",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("from_exchange", sa.String(32), nullable=False),
        sa.Column("to_exchange", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_exchange_failovers_created_at", "exchange_failovers", ["created_at"])

    # 2. Add data_mode column to ohlcv table
    with op.batch_alter_table("ohlcv") as batch_op:
        batch_op.add_column(sa.Column("data_mode", sa.String(24), nullable=False, server_default="LIVE"))


def downgrade() -> None:
    """Downgrade schema: drop exchange_failovers table and data_mode column."""
    with op.batch_alter_table("ohlcv") as batch_op:
        batch_op.drop_column("data_mode")

    op.drop_index("idx_exchange_failovers_created_at", table_name="exchange_failovers")
    op.drop_table("exchange_failovers")
