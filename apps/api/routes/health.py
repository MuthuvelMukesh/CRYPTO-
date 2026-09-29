"""Health check and observability endpoints."""

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from src.config.settings import get_settings
from src.database.cache import CacheService
from src.database.session import check_db_health
from src.utils.time import utc_now

router = APIRouter(tags=["Health & Diagnostics"])

_START_TIME = utc_now()


class ComponentHealth(BaseModel):
    status: str
    details: dict[str, object] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str  # healthy, degraded, unhealthy
    app: str
    version: str
    environment: str
    timestamp: str
    uptime_seconds: float
    components: dict[str, object]


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Comprehensive system health check",
)
async def get_health() -> HealthResponse:
    """Return health status of core services (database, cache, application runtime)."""
    settings = get_settings()
    db_health = await check_db_health()
    cache_health = await CacheService.check_health()

    overall_status = "healthy"
    if db_health.get("status") != "healthy":
        overall_status = "unhealthy"
    elif cache_health.get("status") == "degraded":
        overall_status = "degraded"

    uptime = (utc_now() - _START_TIME).total_seconds()

    return HealthResponse(
        status=overall_status,
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=utc_now().isoformat(),
        uptime_seconds=round(uptime, 2),
        components={
            "database": db_health,
            "cache": cache_health,
        },
    )


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
    return {"live": True}
