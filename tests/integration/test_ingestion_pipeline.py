"""Integration tests for ingestion pipeline, database persistence, and API querying."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import Timeframe
from src.database.models import OHLCV, Asset, Market
from src.ingestion.pipeline import ingest_market_ohlcv, seed_default_universe
from src.ingestion.providers.base import BaseDataProvider, RawCandle, RawTicker


class MockDataProvider(BaseDataProvider):
    """Mock provider returning synthetic valid candles for testing."""

    @property
    def name(self) -> str:
        return "mock_provider"

    @property
    def is_available(self) -> bool:
        return True

    async def fetch_ohlcv(
        self, symbol: str, timeframe: Timeframe = Timeframe.H1, since_ms: int | None = None, limit: int = 100
    ) -> list[RawCandle]:
        base_ms = 1700000000000
        return [
            RawCandle(
                timestamp_ms=base_ms + (i * 3600000),
                open=100.0 + i,
                high=105.0 + i,
                low=95.0 + i,
                close=103.0 + i,
                volume=50.0 + (i * 10),
            )
            for i in range(10)
        ]

    async def fetch_ticker(self, symbol: str) -> RawTicker | None:
        return RawTicker(
            symbol=symbol,
            last_price=110.0,
            timestamp_ms=1700036000000,
        )

    async def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_universe_seeding_and_retrieval(db_session: AsyncSession):
    """Verify seeding creates expected asset catalog and markets."""
    await seed_default_universe(db_session, exchange_id="binance")

    # Verify all 8 assets are present
    res = await db_session.execute(select(Asset))
    assets = res.scalars().all()
    assert len(assets) == 8
    symbols = {a.symbol for a in assets}
    assert "BTC" in symbols
    assert "ETH" in symbols
    assert "SOL" in symbols
    assert "DOGE" in symbols
    assert "PEPE" in symbols

    # Verify markets
    m_res = await db_session.execute(select(Market))
    markets = m_res.scalars().all()
    assert len(markets) == 8


@pytest.mark.asyncio
async def test_ohlcv_ingestion_and_db_persistence(db_session: AsyncSession):
    """Verify market OHLCV ingestion validates and saves candles to DB."""
    await seed_default_universe(db_session, exchange_id="binance")

    provider = MockDataProvider()
    count = await ingest_market_ohlcv(
        session=db_session,
        provider=provider,
        symbol="BTC/USDT",
        market_id="binance:BTC/USDT",
        timeframe=Timeframe.H1,
        limit=10,
    )
    assert count == 10

    # Query back from DB
    res = await db_session.execute(
        select(OHLCV).where(OHLCV.market_id == "binance:BTC/USDT").order_by(OHLCV.time)
    )
    candles = res.scalars().all()
    assert len(candles) == 10
    assert candles[0].close == 103.0
    assert candles[-1].close == 112.0
    assert candles[0].validation_status == "GOOD"


@pytest.mark.asyncio
async def test_asset_and_ohlcv_api_endpoints(client: AsyncClient, db_session: AsyncSession):
    """Verify API endpoints for listing assets and querying OHLCV candles."""
    await seed_default_universe(db_session, exchange_id="binance")

    provider = MockDataProvider()
    await ingest_market_ohlcv(
        session=db_session,
        provider=provider,
        symbol="BTC/USDT",
        market_id="binance:BTC/USDT",
        timeframe=Timeframe.H1,
        limit=10,
    )

    # 1. Test GET /api/v1/assets
    assets_resp = await client.get("/api/v1/assets")
    assert assets_resp.status_code == 200
    assets_data = assets_resp.json()
    assert len(assets_data) == 8

    # 2. Test GET /api/v1/assets/BTC
    btc_resp = await client.get("/api/v1/assets/BTC")
    assert btc_resp.status_code == 200
    btc_data = btc_resp.json()
    assert btc_data["symbol"] == "BTC"
    assert btc_data["asset_class"] == "CORE"
    assert len(btc_data["markets"]) > 0

    # 3. Test GET /api/v1/ohlcv/BTC
    ohlcv_resp = await client.get("/api/v1/ohlcv/BTC?timeframe=1h&limit=5")
    assert ohlcv_resp.status_code == 200
    ohlcv_data = ohlcv_resp.json()
    assert len(ohlcv_data) == 5
    assert ohlcv_data[0]["validation_status"] == "GOOD"
