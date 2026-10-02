"""phase4_survivorship_delisted_at

Revision ID: 7e17d61b2be8
Revises: adbb4e02186f
Create Date: 2026-10-02 15:23:49.844701

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7e17d61b2be8'
down_revision: str | Sequence[str] | None = 'adbb4e02186f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: add delisted_at column to assets and universe_snapshots."""
    with op.batch_alter_table("assets") as batch_op:
        batch_op.add_column(sa.Column("delisted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("idx_assets_delisted_at", ["delisted_at"])

    with op.batch_alter_table("universe_snapshots") as batch_op:
        batch_op.add_column(sa.Column("delisted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema: drop delisted_at column from assets and universe_snapshots."""
    with op.batch_alter_table("universe_snapshots") as batch_op:
        batch_op.drop_column("delisted_at")

    with op.batch_alter_table("assets") as batch_op:
        batch_op.drop_index("idx_assets_delisted_at")
        batch_op.drop_column("delisted_at")
