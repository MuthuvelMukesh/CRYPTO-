"""FastAPI Application entrypoint — v2.0.0."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routes import alerts, assets, backtest, health, meme, paper, scanner, scores, sectors
from src.config.settings import get_settings
from src.database.session import close_db, get_session_factory, init_db
from src.ingestion.pipeline import seed_default_universe
from src.utils.logging import get_logger, setup_logging

logger = get_logger("apps.api.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan management — v2.0."""
    setup_logging()
    settings = get_settings()
    logger.info(
        "application_startup_initiated",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        data_mode=settings.DATA_MODE,
        live_trading_enabled=settings.LIVE_TRADING_ENABLED,  # always False in v2.0
        paper_trading_enabled=settings.PAPER_TRADING_ENABLED,
    )

    # Architecturally enforce live trading disabled at startup
    if settings.LIVE_TRADING_ENABLED:
        raise RuntimeError(
            "LIVE_TRADING_ENABLED=True is not permitted in v2.0. "
            "See settings.enforce_live_trading_disabled."
        )

    try:
        await init_db()
        logger.info("database_initialized_successfully")

        session_factory = get_session_factory()
        async with session_factory() as session:
            await seed_default_universe(session)
        logger.info("default_universe_seeded_successfully")
    except Exception as e:
        logger.error("database_initialization_failed", error=str(e))

    yield

    logger.info("application_shutdown_initiated")
    await close_db()
    logger.info("application_shutdown_completed")


def create_app() -> FastAPI:
    """FastAPI application factory."""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Cryptocurrency Market Intelligence v2.0 — "
            "Quantitative Factor Scanner, Backtesting Engine & Demo Trading Broker. "
            "Non-custodial. No real-money trading."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS — v2.0 security fix (DEFECT-9)
    # allow_origins=["*"] with allow_credentials=True was a security misconfiguration.
    # Now uses configured allow-list from CORS_ALLOWED_ORIGINS setting.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins_list,
        allow_credentials=False,  # v2.0: no session cookies needed
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    )

    # Register routers
    app.include_router(health.router)
    app.include_router(assets.router)
    app.include_router(scores.router)
    app.include_router(backtest.router)
    app.include_router(paper.router)
    app.include_router(meme.router)
    app.include_router(sectors.router)
    app.include_router(alerts.router)
    app.include_router(scanner.router)

    from fastapi import Request
    from fastapi.responses import JSONResponse

    from src.config.exceptions import CryptoIntelligenceError

    @app.exception_handler(CryptoIntelligenceError)
    async def crypto_intelligence_error_handler(request: Request, exc: CryptoIntelligenceError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": type(exc).__name__,
                "message": str(exc),
                "detail": getattr(exc, "details", None) or str(exc),
            },
        )

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
