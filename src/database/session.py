"""Database engine, connection pooling, and session management."""

import time
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config.settings import get_settings
from src.database.models.base import Base
from src.utils.logging import get_logger

logger = get_logger("database.session")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return singleton SQLAlchemy AsyncEngine, initializing if necessary."""
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args = {}

        if settings.is_sqlite:
            connect_args = {"check_same_thread": False}
            _engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DEBUG,
                connect_args=connect_args,
            )
        else:
            _engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DEBUG,
                pool_size=settings.DATABASE_POOL_SIZE,
                max_overflow=settings.DATABASE_MAX_OVERFLOW,
                pool_pre_ping=True,
            )
        logger.info("database_engine_created", url=settings.DATABASE_URL.split("@")[-1])
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return singleton sessionmaker."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def init_db() -> None:
    """Create all database tables asynchronously."""
    settings = get_settings()
    engine = get_engine()
    # Import all models to ensure they are registered with Base.metadata
    import src.database.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.is_sqlite:
            from sqlalchemy import text
            try:
                await conn.execute(text("ALTER TABLE paper_orders ADD COLUMN idempotency_key VARCHAR(64)"))
            except Exception:
                pass  # already exists or new db
    logger.info("database_tables_initialized")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining an isolated async database session."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_health() -> dict[str, object]:
    """Execute a test query to verify database connectivity and measure latency."""
    engine = get_engine()
    start = time.perf_counter()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "status": "healthy",
            "latency_ms": latency_ms,
            "dialect": engine.dialect.name,
        }
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "dialect": engine.dialect.name if engine else "unknown",
        }


async def close_db() -> None:
    """Dispose of engine connections during application shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("database_engine_disposed")
