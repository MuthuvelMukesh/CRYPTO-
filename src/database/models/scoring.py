"""Multi-factor score snapshots and actionable signal models."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class Score(Base):
    """Explainable multi-factor scoring snapshot."""

    __tablename__ = "scores"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(32), ForeignKey("assets.id"), primary_key=True)
    model_type: Mapped[str] = mapped_column(String(32), primary_key=True)  # CORE, ALTCOIN, MEME

    opportunity_score: Mapped[float] = mapped_column(Float, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    trend_score: Mapped[float] = mapped_column(Float, nullable=False)
    momentum_score: Mapped[float] = mapped_column(Float, nullable=False)
    relative_strength_score: Mapped[float] = mapped_column(Float, nullable=False)
    liquidity_score: Mapped[float] = mapped_column(Float, nullable=False)

    breakdown_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    risk_flags: Mapped[list[str]] = mapped_column(JSON, default=list)

    __table_args__ = (
        Index("idx_scores_lookup", "asset_id", "model_type", "time"),
    )


class Signal(Base):
    """Generated research and trading signal."""

    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    asset_id: Mapped[str] = mapped_column(String(32), ForeignKey("assets.id"), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(32), nullable=False)  # MOMENTUM_BREAKOUT, etc.
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # LONG, SHORT
    score: Mapped[float] = mapped_column(Float, nullable=False)
    suggested_stop_loss_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    suggested_take_profit_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    feature_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
