"""Health check and observability endpoints — v2.0.

v2.0 changes:
- Health response now includes data_mode, live_trading_enabled guard state
- Market data freshness check (STALE vs UP)
- Component version matrix in /health/versions
- /health/market-data endpoint showing per-asset freshness
"""

from datetime import UTC, datetime

from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from src.config.constants import HealthStatus
from src.config.settings import get_settings
from src.database.cache import CacheService
from src.database.models import OHLCV, Asset
from src.database.session import check_db_health, get_session_factory
from src.utils.time import utc_now

router = APIRouter(tags=["Health & Diagnostics"])
settings = get_settings()
_START_TIME = utc_now()


class ComponentHealth(BaseModel):
    status: str
    details: dict[str, object] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    environment: str
    data_mode: str
    live_trading_enabled: bool
    paper_trading_enabled: bool
    timestamp: str
    uptime_seconds: float
    components: dict[str, object]


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Comprehensive system health check — v2.0",
)
async def get_health() -> HealthResponse:
    """Return health status of core services with v2.0 data mode and trading guard state."""
    db_health = await check_db_health()
    cache_health = await CacheService.check_health()

    # Check market data freshness
    market_status = await _check_market_data_freshness()

    overall_status = HealthStatus.UP
    if db_health.get("status") != "healthy":
        overall_status = HealthStatus.DOWN
    elif market_status == HealthStatus.STALE:
        overall_status = HealthStatus.DEGRADED
    elif cache_health.get("status") == "degraded":
        overall_status = HealthStatus.DEGRADED

    uptime = (utc_now() - _START_TIME).total_seconds()

    return HealthResponse(
        status=overall_status.value,
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        data_mode=settings.DATA_MODE.value,
        live_trading_enabled=settings.LIVE_TRADING_ENABLED,  # always False
        paper_trading_enabled=settings.PAPER_TRADING_ENABLED,
        timestamp=utc_now().isoformat(),
        uptime_seconds=round(uptime, 2),
        components={
            "database": db_health,
            "cache": cache_health,
            "market_data": {"status": market_status.value},
        },
    )


@router.get(
    "/health/versions",
    summary="Component version matrix — v2.0",
)
async def get_versions() -> dict:
    """Return all component version strings for reproducibility auditing."""
    return {
        "app_version": settings.APP_VERSION,
        "schema_version": settings.SCHEMA_VERSION,
        "feature_version": settings.FEATURE_VERSION,
        "scoring_version": settings.SCORING_VERSION,
        "execution_model_version": settings.EXECUTION_MODEL_VERSION,
        "universe_version": settings.UNIVERSE_VERSION,
        "ingestion_version": settings.INGESTION_VERSION,
        "data_mode": settings.DATA_MODE.value,
        "live_trading_enabled": settings.LIVE_TRADING_ENABLED,
    }


@router.get(
    "/health/market-data",
    summary="Per-asset market data freshness status — v2.0",
)
async def get_market_data_freshness() -> dict:
    """Return how stale each tracked asset's latest candle is."""
    factory = get_session_factory()
    now = datetime.now(UTC)
    threshold = settings.MARKET_DATA_STALE_THRESHOLD_SECONDS
    assets_status = []

    async with factory() as session:
        assets_res = await session.execute(
            select(Asset).where(Asset.is_active.is_(True))
        )
        assets = assets_res.scalars().all()

        for asset in assets:
            candle_res = await session.execute(
                select(OHLCV)
                .where(OHLCV.market_id.like(f"%{asset.id.upper()}%"))
                .order_by(desc(OHLCV.time))
                .limit(1)
            )
            candle = candle_res.scalars().first()
            if not candle:
                assets_status.append({
                    "asset_id": asset.id,
                    "status": HealthStatus.DOWN.value,
                    "reason": "NO_DATA",
                    "latest_candle_time": None,
                    "age_seconds": None,
                })
                continue

            ct = candle.time
            if ct.tzinfo is None:
                ct = ct.replace(tzinfo=UTC)
            age = (now - ct).total_seconds()
            st = HealthStatus.UP if age <= threshold else HealthStatus.STALE
            assets_status.append({
                "asset_id": asset.id,
                "status": st.value,
                "latest_candle_time": ct.isoformat(),
                "age_seconds": round(age, 1),
                "is_fresh": age <= threshold,
            })

    stale_count = sum(1 for a in assets_status if a["status"] != HealthStatus.UP.value)
    return {
        "data_mode": settings.DATA_MODE.value,
        "checked_at": now.isoformat(),
        "threshold_seconds": threshold,
        "total_assets": len(assets_status),
        "stale_count": stale_count,
        "assets": assets_status,
    }


@router.get("/ready", status_code=status.HTTP_200_OK, summary="Kubernetes Readiness Probe")
async def readiness_probe():
    """Readiness probe indicating if the service can receive user traffic."""
    db_health = await check_db_health()
    if db_health.get("status") != "healthy":
        return {"ready": False, "reason": "database_unavailable"}
    return {"ready": True}


@router.get("/live", status_code=status.HTTP_200_OK, summary="Kubernetes Liveness Probe")
async def liveness_probe():
    """Liveness probe indicating if the service process is active."""
    return {"live": True, "version": settings.APP_VERSION}


async def _check_market_data_freshness() -> HealthStatus:
    """Check if any tracked asset has fresh market data."""
    factory = get_session_factory()
    now = datetime.now(UTC)
    threshold = settings.MARKET_DATA_STALE_THRESHOLD_SECONDS

    try:
        async with factory() as session:
            res = await session.execute(
                select(OHLCV).order_by(desc(OHLCV.time)).limit(1)
            )
            latest = res.scalars().first()
            if not latest:
                return HealthStatus.DOWN
            ct = latest.time
            if ct.tzinfo is None:
                ct = ct.replace(tzinfo=UTC)
            age = (now - ct).total_seconds()
            return HealthStatus.UP if age <= threshold else HealthStatus.STALE
    except Exception:
        return HealthStatus.DOWN
