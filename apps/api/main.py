"""FastAPI Application entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routes import assets, backtest, health, paper, scores
from src.config.settings import get_settings
from src.database.session import close_db, get_session_factory, init_db
from src.ingestion.pipeline import seed_default_universe
from src.utils.logging import get_logger, setup_logging

logger = get_logger("apps.api.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan management for initialization and clean teardown."""
    setup_logging()
    settings = get_settings()
    logger.info("application_startup_initiated", app=settings.APP_NAME, version=settings.APP_VERSION)

    # Initialize database tables and seed initial universe
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

    # Clean shutdown
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
            "Cryptocurrency Market Intelligence, Quantitative Factor Scanner, "
            "Backtesting Engine & Paper Trading Broker API."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router)
    app.include_router(assets.router)
    app.include_router(scores.router)
    app.include_router(backtest.router)
    app.include_router(paper.router)

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
