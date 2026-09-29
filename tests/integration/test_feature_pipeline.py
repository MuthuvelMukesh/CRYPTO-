"""Integration tests for end-to-end feature calculation and database persistence."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import Timeframe
from src.database.models import Feature
from src.features.pipeline import calculate_and_store_asset_features
from src.ingestion.pipeline import ingest_market_ohlcv, seed_default_universe
from src.ingestion.providers.base import BaseDataProvider, RawCandle, RawTicker


class FeatureMockProvider(BaseDataProvider):
    """Mock provider with 60 hourly candles."""

    @property
    def name(self) -> str:
        return "feature_mock"

    @property
    def is_available(self) -> bool:
        return True

    async def fetch_ohlcv(
        self, symbol: str, timeframe: Timeframe = Timeframe.H1, since_ms: int | None = None, limit: int = 100
    ) -> list[RawCandle]:
        base_ms = 1700000000000
        # Multiplier depends on symbol
        mult = 1.0
        if "BTC" in symbol:
            mult = 400.0
        elif "ETH" in symbol:
            mult = 25.0

        return [
            RawCandle(
                timestamp_ms=base_ms + (i * 3600000),
                open=(100.0 + i) * mult,
                high=(105.0 + i) * mult,
                low=(95.0 + i) * mult,
                close=(103.0 + i) * mult,
                volume=100.0 + (i * 5),
            )
            for i in range(60)
        ]

    async def fetch_ticker(self, symbol: str) -> RawTicker | None:
        return None

    async def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_end_to_end_feature_pipeline(db_session: AsyncSession):
    """Verify feature calculation pipeline runs on stored candles and persists factors."""
    await seed_default_universe(db_session, exchange_id="binance")

    provider = FeatureMockProvider()

    # Ingest candles for BTC and SOL
    for sym in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]:
        await ingest_market_ohlcv(
            session=db_session,
            provider=provider,
            symbol=sym,
            market_id=f"binance:{sym}",
            timeframe=Timeframe.H1,
            limit=60,
        )

    # Compute features for SOL
    feat = await calculate_and_store_asset_features(
        session=db_session,
        asset_id="SOL",
        timeframe=Timeframe.H1,
        exchange_id="binance",
    )

    assert feat is not None
    assert feat.asset_id == "SOL"
    assert feat.timeframe == "1h"
    assert feat.return_1d is not None
    assert feat.ema20_ratio is not None
    assert feat.ema20_ratio > 1.0
    assert feat.atr_14_pct is not None
    assert feat.volume_to_20d_avg is not None

    # Query back from DB
    res = await db_session.execute(
        select(Feature).where(Feature.asset_id == "SOL")
    )
    queried = res.scalar_one_or_none()
    assert queried is not None
    assert queried.asset_id == "SOL"
    assert queried.return_1d is not None
