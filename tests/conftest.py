"""Pytest configuration, database fixtures, and test HTTP client."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import src.database.models  # noqa: F401
from apps.api.deps import get_db
from apps.api.main import create_app
from src.config.settings import Settings, get_settings
from src.database.models.base import Base

# Test database URL: isolated in-memory SQLite database
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Return test settings with SQLite memory database."""
    return Settings(
        ENVIRONMENT="testing",
        DATABASE_URL=TEST_DB_URL,
        REDIS_URL="redis://localhost:9999/0",  # Unused port -> forces in-memory cache fallback
        LOG_LEVEL="DEBUG",
    )


@pytest.fixture
async def test_engine(test_settings: Settings):
    """Create isolated async SQLite database engine for testing."""
    engine = create_async_engine(
        test_settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield isolated database session for a test."""
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(test_engine, test_settings: Settings) -> AsyncGenerator[AsyncClient, None]:
    """Yield async HTTP client connected to FastAPI app with test DB override."""
    app = create_app()

    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: test_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
