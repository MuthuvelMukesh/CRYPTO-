"""phase2_numeric_precision_and_ledger_immutability

Revision ID: ef40759b6eb4
Revises:
Create Date: 2026-10-02 15:05:55.181712

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ef40759b6eb4'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: convert Float monetary/quantity columns to Numeric(28, 10) and enforce append-only triggers."""
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # 1. paper_accounts
    with op.batch_alter_table("paper_accounts") as batch_op:
        batch_op.alter_column("starting_balance", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("cash_balance", existing_type=sa.Float(), type_=sa.Numeric(28, 10))

    # 2. paper_orders
    with op.batch_alter_table("paper_orders") as batch_op:
        batch_op.alter_column("quantity", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("limit_price", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("stop_price", existing_type=sa.Float(), type_=sa.Numeric(28, 10))

    # 3. paper_fills
    with op.batch_alter_table("paper_fills") as batch_op:
        batch_op.alter_column("fill_price", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("quantity", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("fee_usd", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("slippage_usd", existing_type=sa.Float(), type_=sa.Numeric(28, 10))

    # 4. paper_positions
    with op.batch_alter_table("paper_positions") as batch_op:
        batch_op.alter_column("quantity", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("avg_entry_price", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("current_price", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("unrealized_pnl", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("realized_pnl", existing_type=sa.Float(), type_=sa.Numeric(28, 10))

    # 5. paper_equity
    with op.batch_alter_table("paper_equity") as batch_op:
        batch_op.alter_column("equity", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("cash", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("invested_capital", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("unrealized_pnl", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("realized_pnl", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("drawdown_pct", existing_type=sa.Float(), type_=sa.Numeric(28, 10))

    # 6. portfolio_snapshots
    with op.batch_alter_table("portfolio_snapshots") as batch_op:
        batch_op.alter_column("gross_exposure", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("net_exposure", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("meme_exposure_pct", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("max_single_position_pct", existing_type=sa.Float(), type_=sa.Numeric(28, 10))

    # 7. ledger_events
    with op.batch_alter_table("ledger_events") as batch_op:
        batch_op.alter_column("quantity", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("price", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("amount_usd", existing_type=sa.Float(), type_=sa.Numeric(28, 10))
        batch_op.alter_column("cash_balance_after", existing_type=sa.Float(), type_=sa.Numeric(28, 10))

    # 8. Database triggers for ledger immutability
    if is_sqlite:
        op.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_ledger_events_no_update
            BEFORE UPDATE ON ledger_events
            BEGIN
                SELECT RAISE(ABORT, 'ledger_events is append-only: updates are prohibited');
            END;
        """)
        op.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_ledger_events_no_delete
            BEFORE DELETE ON ledger_events
            BEGIN
                SELECT RAISE(ABORT, 'ledger_events is append-only: deletes are prohibited');
            END;
        """)
    else:
        op.execute("""
            CREATE OR REPLACE FUNCTION trg_prevent_ledger_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'ledger_events is append-only: updates and deletes are prohibited';
            END;
            $$ LANGUAGE plpgsql;
        """)
        op.execute("""
            DROP TRIGGER IF EXISTS trg_ledger_events_immutable ON ledger_events;
            CREATE TRIGGER trg_ledger_events_immutable
            BEFORE UPDATE OR DELETE ON ledger_events
            FOR EACH ROW EXECUTE FUNCTION trg_prevent_ledger_mutation();
        """)


def downgrade() -> None:
    """Downgrade schema: drop triggers and revert Numeric(28, 10) back to Float."""
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # 1. Drop immutability triggers
    if is_sqlite:
        op.execute("DROP TRIGGER IF EXISTS trg_ledger_events_no_update;")
        op.execute("DROP TRIGGER IF EXISTS trg_ledger_events_no_delete;")
    else:
        op.execute("DROP TRIGGER IF EXISTS trg_ledger_events_immutable ON ledger_events;")
        op.execute("DROP FUNCTION IF EXISTS trg_prevent_ledger_mutation();")

    # 2. Revert columns to Float
    with op.batch_alter_table("ledger_events") as batch_op:
        batch_op.alter_column("quantity", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("price", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("amount_usd", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("cash_balance_after", existing_type=sa.Numeric(28, 10), type_=sa.Float())

    with op.batch_alter_table("portfolio_snapshots") as batch_op:
        batch_op.alter_column("gross_exposure", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("net_exposure", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("meme_exposure_pct", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("max_single_position_pct", existing_type=sa.Numeric(28, 10), type_=sa.Float())

    with op.batch_alter_table("paper_equity") as batch_op:
        batch_op.alter_column("equity", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("cash", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("invested_capital", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("unrealized_pnl", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("realized_pnl", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("drawdown_pct", existing_type=sa.Numeric(28, 10), type_=sa.Float())

    with op.batch_alter_table("paper_positions") as batch_op:
        batch_op.alter_column("quantity", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("avg_entry_price", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("current_price", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("unrealized_pnl", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("realized_pnl", existing_type=sa.Numeric(28, 10), type_=sa.Float())

    with op.batch_alter_table("paper_fills") as batch_op:
        batch_op.alter_column("fill_price", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("quantity", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("fee_usd", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("slippage_usd", existing_type=sa.Numeric(28, 10), type_=sa.Float())

    with op.batch_alter_table("paper_orders") as batch_op:
        batch_op.alter_column("quantity", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("limit_price", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("stop_price", existing_type=sa.Numeric(28, 10), type_=sa.Float())

    with op.batch_alter_table("paper_accounts") as batch_op:
        batch_op.alter_column("starting_balance", existing_type=sa.Numeric(28, 10), type_=sa.Float())
        batch_op.alter_column("cash_balance", existing_type=sa.Numeric(28, 10), type_=sa.Float())
