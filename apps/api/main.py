"""FastAPI Application entrypoint — Platform v3.0.

Hardened foundation:
- Fail-fast startup on database failure or insecure production secrets
- Hybrid authentication (API Key & JWT Bearer) enforced across all non-health routes
- RFC 7807 problem+json error formatting
- Request ID tracing and propagation
- Sliding-window rate limiting
- CSRF protection for browser sessions
- Constant-query scanner endpoint and SSE streams
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.api.deps import get_current_auth
from apps.api.middleware import (
    CSRFProtectionMiddleware,
    RateLimiterMiddleware,
    RequestIdMiddleware,
)
from apps.api.problem import (
    problem_crypto_error_handler,
    problem_generic_exception_handler,
    problem_http_exception_handler,
    problem_validation_exception_handler,
)
from apps.api.routes import (
    alerts,
    assets,
    auth,
    backtest,
    health,
    meme,
    paper,
    research,
    scanner,
    scores,
    sectors,
    streams,
)
from src.config.exceptions import CryptoIntelligenceError
from src.config.settings import get_settings
from src.database.session import close_db, get_session_factory, init_db
from src.ingestion.pipeline import seed_default_universe
from src.observability.metrics import PrometheusMetricsMiddleware
from src.utils.logging import get_logger, setup_logging

logger = get_logger("apps.api.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan management — Platform v3.0."""
    setup_logging()
    settings = get_settings()

    logger.info(
        "application_startup_initiated",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        data_mode=settings.DATA_MODE.value,
        live_trading_enabled=settings.LIVE_TRADING_ENABLED,  # always False in Platform v3.0
        paper_trading_enabled=settings.PAPER_TRADING_ENABLED,
    )

    # 1. Enforce live trading disabled invariant
    if settings.LIVE_TRADING_ENABLED:
        raise RuntimeError(
            "LIVE_TRADING_ENABLED=True is strictly prohibited by system invariants. "
            "The platform is research and paper-trading only."
        )

    # 2. Enforce secure production secrets
    settings.validate_production_security()

    # 3. Database initialization: fail fast on startup if database is unreachable
    try:
        await init_db()
        logger.info("database_initialized_successfully")

        session_factory = get_session_factory()
        async with session_factory() as session:
            await seed_default_universe(session)
        logger.info("default_universe_seeded_successfully")
    except Exception as e:
        logger.critical("database_initialization_failed_fast", error=str(e))
        raise RuntimeError(f"Database initialization failed during startup lifespan: {e}") from e

    yield

    logger.info("application_shutdown_initiated")
    await close_db()
    logger.info("application_shutdown_completed")


def create_app() -> FastAPI:
    """FastAPI application factory for Platform v3.0."""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Cryptocurrency Market Intelligence & Quantitative Workstation v3.0. "
            "Factor Scanner, Robust Backtesting, Real-time Streaming, and Paper Trading. "
            "Non-custodial research platform. No live execution."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Middlewares (Executed in reverse order of addition: RequestId -> RateLimiter -> CSRF -> CORS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID", "X-API-Key", "X-CSRF-Token"],
    )
    app.add_middleware(CSRFProtectionMiddleware)
    app.add_middleware(RateLimiterMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(PrometheusMetricsMiddleware)

    # RFC 7807 Problem+JSON Exception Handlers
    app.add_exception_handler(StarletteHTTPException, problem_http_exception_handler)
    app.add_exception_handler(RequestValidationError, problem_validation_exception_handler)
    app.add_exception_handler(CryptoIntelligenceError, problem_crypto_error_handler)
    app.add_exception_handler(Exception, problem_generic_exception_handler)

    # Unauthenticated Routers
    app.include_router(health.router)
    app.include_router(auth.router)

    # Authenticated Routers (Enforce valid API Key or JWT token on every route)
    auth_dep = [Depends(get_current_auth)]
    app.include_router(scanner.router, dependencies=auth_dep)
    app.include_router(assets.router, dependencies=auth_dep)
    app.include_router(scores.router, dependencies=auth_dep)
    app.include_router(backtest.router, dependencies=auth_dep)
    app.include_router(paper.router, dependencies=auth_dep)
    app.include_router(meme.router, dependencies=auth_dep)
    app.include_router(sectors.router, dependencies=auth_dep)
    app.include_router(alerts.router, dependencies=auth_dep)
    app.include_router(research.router, dependencies=auth_dep)
    app.include_router(streams.router, dependencies=auth_dep)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "apps.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )
