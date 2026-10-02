"""Live Scanner Pipeline — v2.0.

Orchestrates the full scan cycle:
  1. Fetch latest prices / OHLCV for all tracked assets
  2. Compute features
  3. Compute scores
  4. Write ScannerSnapshot rows (for forward return attribution)
  5. Publish result to an in-memory cache for dashboard consumption

Freshness tracking:
  - Every ScannerSnapshot carries data_age_seconds and data_fresh flag
  - Stale assets are flagged STALE but not silently dropped
  - The scanner result always says how old the underlying data is
"""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import DataMode, DataQualityStatus
from src.config.settings import get_settings
from src.database.models import OHLCV, ScannerSnapshot, Score
from src.database.session import get_session_factory, init_db
from src.ingestion.live_ingestor import run_ingestion_cycle
from src.utils.logging import get_logger

logger = get_logger("scanner.pipeline")
settings = get_settings()


@dataclass
class ScannerAssetResult:
    """Scanner result for a single asset with full data provenance."""
    asset_id: str
    rank: int
    opportunity_score: float
    momentum_score: float | None
    trend_score: float | None
    volume_score: float | None
    risk_score: float | None
    price: float | None
    price_age_seconds: float | None
    data_fresh: bool
    data_mode: DataMode
    data_quality: DataQualityStatus
    risk_flags: list[str] = field(default_factory=list)
    model_type: str = ""
    scanned_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ScannerCycleResult:
    """Full scanner cycle output with provenance metadata."""
    cycle_id: str
    started_at: datetime
    completed_at: datetime | None
    data_mode: DataMode
    assets: list[ScannerAssetResult] = field(default_factory=list)
    stale_count: int = 0
    fresh_count: int = 0
    error_count: int = 0
    ingestion_triggered: bool = False

    @property
    def duration_seconds(self) -> float:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    @property
    def is_fresh(self) -> bool:
        return self.stale_count == 0 and self.fresh_count > 0

    def to_dict(self) -> dict:
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "data_mode": self.data_mode.value,
            "duration_seconds": self.duration_seconds,
            "assets_ranked": len(self.assets),
            "fresh_count": self.fresh_count,
            "stale_count": self.stale_count,
            "is_fresh": self.is_fresh,
            "rankings": [
                {
                    "rank": a.rank,
                    "asset_id": a.asset_id,
                    "opportunity_score": a.opportunity_score,
                    "price": a.price,
                    "data_fresh": a.data_fresh,
                    "price_age_seconds": a.price_age_seconds,
                    "data_quality": a.data_quality.value,
                    "risk_flags": a.risk_flags,
                    "model_type": a.model_type,
                }
                for a in self.assets
            ],
        }


class LiveScannerPipeline:
    """Full-cycle live scanner with data freshness enforcement — v2.0.

    Responsibilities:
    - Trigger market data ingestion if data is stale
    - Score all assets
    - Write ScannerSnapshot rows
    - Surface explicit staleness signals in output
    """

    def __init__(self) -> None:
        import uuid
        self._cycle_id = str(uuid.uuid4())[:8]

    async def run_scan_cycle(
        self,
        session: AsyncSession,
        trigger_ingestion: bool = False,
    ) -> ScannerCycleResult:
        """Execute one complete scan cycle.

        Args:
            session: async DB session
            trigger_ingestion: if True, fetch fresh candles from exchange first

        Returns:
            ScannerCycleResult with ranked assets and full provenance
        """
        import uuid
        cycle_id = str(uuid.uuid4())[:12]
        started_at = datetime.now(UTC)

        result = ScannerCycleResult(
            cycle_id=cycle_id,
            started_at=started_at,
            completed_at=None,
            data_mode=settings.DATA_MODE,
        )

        logger.info(
            "scanner_cycle_started",
            cycle_id=cycle_id,
            data_mode=settings.DATA_MODE,
            trigger_ingestion=trigger_ingestion,
        )

        # 1. Optionally trigger ingestion to freshen data
        if trigger_ingestion and settings.MARKET_DATA_ENABLED:
            try:
                ingest_result = await run_ingestion_cycle(
                    compute_features=True,
                    compute_scores=True,
                )
                result.ingestion_triggered = True
                logger.info(
                    "scanner_ingestion_triggered",
                    succeeded=ingest_result.assets_succeeded,
                    failed=ingest_result.assets_failed,
                )
            except Exception as e:
                logger.warning("scanner_ingestion_failed", error=str(e))

        # 2. Load all scores from DB
        scores_res = await session.execute(
            select(Score)
            .order_by(desc(Score.opportunity_score))
        )
        scores = scores_res.scalars().all()

        if not scores:
            logger.warning("scanner_no_scores_available")
            result.completed_at = datetime.now(UTC)
            result.error_count = 1
            return result

        # 3. Build ranked results with freshness checks
        now_utc = datetime.now(UTC)
        threshold = settings.SCANNER_STALE_THRESHOLD_SECONDS

        for rank, score in enumerate(scores, start=1):
            # Get latest price and its age
            price_val, age_seconds, fresh = await self._get_price_with_age(
                session, score.asset_id, now_utc, threshold
            )

            quality = DataQualityStatus.GOOD if fresh else DataQualityStatus.STALE

            asset_result = ScannerAssetResult(
                asset_id=score.asset_id,
                rank=rank,
                opportunity_score=round(score.opportunity_score, 2),
                momentum_score=getattr(score, "momentum_score", None),
                trend_score=getattr(score, "trend_score", None),
                volume_score=getattr(score, "volume_score", None),
                risk_score=getattr(score, "risk_score", None),
                price=price_val,
                price_age_seconds=age_seconds,
                data_fresh=fresh,
                data_mode=settings.DATA_MODE,
                data_quality=quality,
                risk_flags=score.risk_flags or [],
                model_type=getattr(score, "model_type", ""),
            )
            result.assets.append(asset_result)

            if fresh:
                result.fresh_count += 1
            else:
                result.stale_count += 1

        # 4. Write ScannerSnapshot rows
        await self._write_snapshots(session, result)

        result.completed_at = datetime.now(UTC)
        logger.info(
            "scanner_cycle_completed",
            cycle_id=cycle_id,
            assets=len(result.assets),
            fresh=result.fresh_count,
            stale=result.stale_count,
            duration=result.duration_seconds,
        )
        return result

    async def _get_price_with_age(
        self,
        session: AsyncSession,
        asset_id: str,
        now: datetime,
        threshold_seconds: float,
    ) -> tuple[float | None, float | None, bool]:
        """Return (price, age_seconds, is_fresh) for an asset."""
        res = await session.execute(
            select(OHLCV)
            .where(OHLCV.market_id.like(f"%{asset_id.upper()}%"))
            .order_by(desc(OHLCV.time))
            .limit(1)
        )
        candle = res.scalars().first()
        if not candle or not candle.close or candle.close <= 0:
            return None, None, False

        candle_time = candle.time
        if candle_time.tzinfo is None:
            candle_time = candle_time.replace(tzinfo=UTC)
        age = (now - candle_time).total_seconds()
        fresh = age <= threshold_seconds
        return float(candle.close), round(age, 1), fresh

    async def _write_snapshots(
        self,
        session: AsyncSession,
        result: ScannerCycleResult,
    ) -> None:
        """Write immutable ScannerSnapshot rows for research attribution."""
        for asset_result in result.assets:
            session.add(ScannerSnapshot(
                snapshot_time=result.started_at,
                asset_id=asset_result.asset_id,
                rank=asset_result.rank,
                opportunity_score=asset_result.opportunity_score,
                momentum_score=asset_result.momentum_score,
                trend_score=asset_result.trend_score,
                volume_score=asset_result.volume_score,
                risk_score=asset_result.risk_score,
                price_at_snapshot=asset_result.price,
                data_mode=asset_result.data_mode.value,
                data_fresh=asset_result.data_fresh,
                data_age_seconds=asset_result.price_age_seconds,
            ))
        try:
            await session.commit()
        except Exception as e:
            logger.warning("scanner_snapshot_write_failed", error=str(e))


# ─── Module-level cache of most recent scanner result ────────────────────────
_last_scan_result: ScannerCycleResult | None = None


def get_last_scan_result() -> ScannerCycleResult | None:
    """Return the cached result from the most recent scan cycle."""
    return _last_scan_result


async def run_continuous_scanner(interval_seconds: int = 60) -> None:
    """Run the live scanner loop indefinitely.

    Each cycle:
    1. Triggers market data ingestion
    2. Scores all assets
    3. Writes ScannerSnapshot rows
    4. Updates the in-memory cache
    """
    global _last_scan_result
    await init_db()
    factory = get_session_factory()
    pipeline = LiveScannerPipeline()

    logger.info("continuous_scanner_started", interval_seconds=interval_seconds)

    while True:
        try:
            async with factory() as session:
                _last_scan_result = await pipeline.run_scan_cycle(
                    session, trigger_ingestion=True
                )
        except Exception as e:
            logger.error("scanner_cycle_fatal_error", error=str(e))

        await asyncio.sleep(interval_seconds)
