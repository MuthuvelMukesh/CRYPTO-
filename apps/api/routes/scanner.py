"""Scanner API routes — v2.0.

Exposes the live scanner rankings, data freshness status, and snapshot history.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, select

from src.config.constants import HealthStatus
from src.config.settings import get_settings
from src.database.models import OHLCV, Score, ScannerSnapshot
from src.database.session import get_session_factory

router = APIRouter(prefix="/api/v1/scanner", tags=["Live Scanner"])
settings = get_settings()


@router.get(
    "/rankings",
    summary="Get latest scanner rankings with data freshness metadata",
)
async def get_scanner_rankings(
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    """Return current scanner rankings.

    Response includes per-asset data_fresh flag and price_age_seconds
    so clients always know how current the underlying data is.
    """
    factory = get_session_factory()
    now = datetime.now(UTC)
    threshold = settings.SCANNER_STALE_THRESHOLD_SECONDS

    async with factory() as session:
        scores_res = await session.execute(
            select(Score)
            .order_by(desc(Score.opportunity_score))
            .limit(limit)
        )
        scores = scores_res.scalars().all()

        if not scores:
            return {
                "data_mode": settings.DATA_MODE.value,
                "scanner_status": HealthStatus.DOWN.value,
                "message": "No scanner data available. Run market data ingestion first.",
                "rankings": [],
                "ranked_at": None,
            }

        rankings = []
        stale_count = 0
        for rank, score in enumerate(scores, start=1):
            # Get latest price and age
            price_res = await session.execute(
                select(OHLCV)
                .where(OHLCV.market_id.like(f"%{score.asset_id.upper()}%"))
                .order_by(desc(OHLCV.time))
                .limit(1)
            )
            candle = price_res.scalars().first()
            price = None
            age_seconds = None
            data_fresh = False

            if candle and candle.close and candle.close > 0:
                ct = candle.time
                if ct.tzinfo is None:
                    ct = ct.replace(tzinfo=UTC)
                age_seconds = round((now - ct).total_seconds(), 1)
                data_fresh = age_seconds <= threshold
                price = float(candle.close)

            if not data_fresh:
                stale_count += 1

            rankings.append({
                "rank": rank,
                "asset_id": score.asset_id,
                "opportunity_score": round(score.opportunity_score, 2),
                "momentum_score": getattr(score, "momentum_score", None),
                "trend_score": getattr(score, "trend_score", None),
                "volume_score": getattr(score, "volume_score", None),
                "risk_score": getattr(score, "risk_score", None),
                "quality_score": getattr(score, "quality_score", None),
                "price": price,
                "price_age_seconds": age_seconds,
                "data_fresh": data_fresh,
                "risk_flags": score.risk_flags or [],
                "model_type": getattr(score, "model_type", ""),
            })

        scanner_status = (
            HealthStatus.STALE.value if stale_count > len(rankings) / 2
            else HealthStatus.UP.value
        )

        return {
            "data_mode": settings.DATA_MODE.value,
            "scanner_status": scanner_status,
            "stale_threshold_seconds": threshold,
            "total_assets": len(rankings),
            "stale_count": stale_count,
            "fresh_count": len(rankings) - stale_count,
            "ranked_at": now.isoformat(),
            "rankings": rankings,
        }


@router.get(
    "/status",
    summary="Scanner operational status and data freshness summary",
)
async def get_scanner_status() -> dict:
    """Return scanner data mode, freshness, and operational state."""
    factory = get_session_factory()
    now = datetime.now(UTC)

    async with factory() as session:
        latest_res = await session.execute(
            select(OHLCV).order_by(desc(OHLCV.time)).limit(1)
        )
        latest = latest_res.scalars().first()

        score_res = await session.execute(select(Score).limit(1))
        has_scores = score_res.scalar_one_or_none() is not None

    age_seconds = None
    data_status = HealthStatus.DOWN.value
    if latest:
        ct = latest.time
        if ct.tzinfo is None:
            ct = ct.replace(tzinfo=UTC)
        age_seconds = round((now - ct).total_seconds(), 1)
        data_status = (
            HealthStatus.UP.value
            if age_seconds <= settings.MARKET_DATA_STALE_THRESHOLD_SECONDS
            else HealthStatus.STALE.value
        )

    return {
        "data_mode": settings.DATA_MODE.value,
        "live_trading_enabled": settings.LIVE_TRADING_ENABLED,
        "market_data_status": data_status,
        "latest_candle_age_seconds": age_seconds,
        "has_scores": has_scores,
        "stale_threshold_seconds": settings.MARKET_DATA_STALE_THRESHOLD_SECONDS,
        "checked_at": now.isoformat(),
    }


@router.get(
    "/snapshots",
    summary="Historical scanner snapshot records for research attribution",
)
async def get_scanner_snapshots(
    asset_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    """Return historical scanner snapshot rows.

    These are the point-in-time ranking records used for forward return
    attribution and scanner quality measurement.
    """
    factory = get_session_factory()
    async with factory() as session:
        q = select(ScannerSnapshot).order_by(desc(ScannerSnapshot.snapshot_time))
        if asset_id:
            q = q.where(ScannerSnapshot.asset_id == asset_id.upper())
        q = q.limit(limit)
        res = await session.execute(q)
        snaps = res.scalars().all()

    return {
        "count": len(snaps),
        "snapshots": [
            {
                "id": s.id,
                "snapshot_time": s.snapshot_time.isoformat(),
                "asset_id": s.asset_id,
                "rank": s.rank,
                "opportunity_score": s.opportunity_score,
                "price_at_snapshot": s.price_at_snapshot,
                "data_fresh": s.data_fresh,
                "data_age_seconds": s.data_age_seconds,
                "data_mode": s.data_mode,
                "fwd_return_1h": s.fwd_return_1h,
                "fwd_return_24h": s.fwd_return_24h,
                "fwd_return_7d": s.fwd_return_7d,
            }
            for s in snaps
        ],
    }
