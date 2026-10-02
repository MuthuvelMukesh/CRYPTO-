"""v2.0 Ledger event log for authoritative paper trading accounting.

Every state-changing paper trading action writes an immutable ledger event.
This enables restart recovery, audit trails, and idempotent reconciliation.
"""

import re
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, Text, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base
from src.utils.time import utc_now


class LedgerEvent(Base):
    """Immutable audit log for all paper trading state changes — v2.0 / v3.0.

    Design principles:
    - Append-only: events are never updated or deleted
    - Idempotent: event_id is unique; duplicate processing is safe to detect
    - Self-contained: each row carries enough context to reconstruct state
    """

    __tablename__ = "ledger_events"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    asset_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    cash_balance_after: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    # JSON blob carrying event-specific payload
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # data_mode at the time of this event (LIVE / HISTORICAL / SYNTHETIC_TEST)
    data_mode: Mapped[str] = mapped_column(String(24), nullable=False, default="LIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )

    __table_args__ = (
        Index("idx_ledger_account_time", "account_id", "created_at"),
        Index("idx_ledger_order", "order_id"),
    )


@event.listens_for(LedgerEvent, "before_update")
def _prevent_ledger_update(mapper, connection, target):
    raise ValueError("LedgerEvent is append-only: updates are prohibited.")


@event.listens_for(LedgerEvent, "before_delete")
def _prevent_ledger_delete(mapper, connection, target):
    raise ValueError("LedgerEvent is append-only: deletes are prohibited.")


@event.listens_for(Engine, "before_cursor_execute")
def _prevent_cursor_ledger_mutation(conn, cursor, statement, parameters, context, executemany):
    stmt_upper = statement.strip().upper()
    if stmt_upper.startswith("UPDATE") or stmt_upper.startswith("DELETE"):
        if re.search(r"\b(UPDATE|DELETE\s+FROM)\s+[\"']?(?:\w+\.)?ledger_events[\"']?\b", stmt_upper, re.IGNORECASE):
            raise ValueError("LedgerEvent is append-only: SQL UPDATE and DELETE on ledger_events are prohibited.")

