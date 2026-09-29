"""Quantitative feature models."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class Feature(Base):
    """Calculated quantitative features at time T."""

    __tablename__ = "features"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(32), ForeignKey("assets.id"), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True)

    # Momentum
    return_1d: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_3d: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_14d: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_30d: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_90d: Mapped[float | None] = mapped_column(Float, nullable=True)
    momentum_acceleration: Mapped[float | None] = mapped_column(Float, nullable=True)
    volatility_adjusted_momentum: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relative Strength
    rs_btc_30d: Mapped[float | None] = mapped_column(Float, nullable=True)
    rs_eth_30d: Mapped[float | None] = mapped_column(Float, nullable=True)
    rs_sector_30d: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Trend
    ema20_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    ema50_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    ema200_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    adx_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr_14_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Volume & Liquidity
    volume_to_20d_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_acceleration: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnover_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    spread_est_bps: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Volatility & Risk
    realized_vol_30d: Mapped[float | None] = mapped_column(Float, nullable=True)
    downside_vol_30d: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_90d: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("idx_features_lookup", "asset_id", "timeframe", "time"),
    )
