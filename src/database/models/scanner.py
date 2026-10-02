"""v2.0 Scanner snapshot and universe snapshot models.

ScannerSnapshot: point-in-time record of scanner rankings. Used for:
- Forward return attribution (signal quality measurement)
- Bias testing
- Research reproducibility

UniverseSnapshot: point-in-time record of which assets were in the
tracked universe and their metadata. Required for point-in-time backtesting.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base
from src.utils.time import utc_now


class ScannerSnapshot(Base):
    """Point-in-time scanner ranking snapshot — v2.0.

    Written by the LiveScannerPipeline at the end of each scan cycle.
    Used to track signal forward returns and measure scanner quality over time.

    Rule: never modify historical snapshots. Each scan is a new row.
    """

    __tablename__ = "scanner_snapshots"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    snapshot_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True, default=utc_now
    )
    asset_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False, default="1h")

    # Rankings and scores at snapshot time
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    opportunity_score: Mapped[float] = mapped_column(Float, nullable=False)
    momentum_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    trend_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Market data at snapshot time (for forward return calc)
    price_at_snapshot: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Forward returns (filled in later by attribution job)
    fwd_return_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    fwd_return_4h: Mapped[float | None] = mapped_column(Float, nullable=True)
    fwd_return_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    fwd_return_7d: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Provenance
    data_mode: Mapped[str] = mapped_column(String(24), nullable=False, default="LIVE")
    # Was the market data fresh at snapshot time?
    data_fresh: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Staleness age in seconds at time of snapshot
    data_age_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("idx_scanner_snap_time_asset", "snapshot_time", "asset_id"),
        Index("idx_scanner_snap_asset", "asset_id", "snapshot_time"),
    )


class UniverseSnapshot(Base):
    """Point-in-time asset universe membership record — v2.0.

    Captures which assets were in the scanner universe at a given time.
    Required for point-in-time-correct backtesting to avoid look-ahead bias.

    Rule: a new row per asset per day. Historical rows are immutable.
    """

    __tablename__ = "universe_snapshots"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    snapshot_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    asset_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    exchange_id: Mapped[str] = mapped_column(String(32), nullable=False)
    market_id: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(24), nullable=False)
    primary_sector: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    delisted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Inclusion criteria at snapshot time
    volume_24h_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    liquidity_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Why was this asset included / excluded?
    inclusion_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    data_mode: Mapped[str] = mapped_column(String(24), nullable=False, default="LIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    __table_args__ = (
        Index("idx_universe_snap_date_asset", "snapshot_date", "asset_id"),
    )
