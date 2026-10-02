"""v2.0 Ledger event log for authoritative paper trading accounting.

Every state-changing paper trading action writes an immutable ledger event.
This enables restart recovery, audit trails, and idempotent reconciliation.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base
from src.utils.time import utc_now


class LedgerEvent(Base):
    """Immutable audit log for all paper trading state changes — v2.0.

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
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    cash_balance_after: Mapped[float | None] = mapped_column(Float, nullable=True)
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
