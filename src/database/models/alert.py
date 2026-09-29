"""System alerts, notifications, and operational event audit models."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base
from src.utils.time import utc_now


class Alert(Base):
    """Triggered quantitative or risk alert."""

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)  # MOMENTUM_BREAKOUT, RISK_REGIME_CHANGE
    severity: Mapped[str] = mapped_column(String(16), default="INFO")  # INFO, WARNING, CRITICAL
    asset_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message: Mapped[str] = mapped_column(String(256), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)


class SystemEvent(Base):
    """Operational health audit log (API failures, rate limits, provider failovers)."""

    __tablename__ = "system_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)  # RATE_LIMIT, PROVIDER_FAILOVER
    service: Mapped[str] = mapped_column(String(32), nullable=False)  # ingestion, api, paper
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
