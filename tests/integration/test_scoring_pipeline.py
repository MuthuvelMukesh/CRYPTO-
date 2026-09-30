"""Integration tests for scoring engine, database persistence, and scoring REST endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import Timeframe
from src.database.models import Score
from src.features.pipeline import calculate_and_store_asset_features
from src.ingestion.pipeline import ingest_market_ohlcv, seed_default_universe
from src.ingestion.providers.base import BaseDataProvider, RawCandle, RawTicker
from src.scoring.engine import score_single_asset, score_universe


class ScoringMockProvider(BaseDataProvider):
    """Mock provider with 60 candles."""

    @property
    def name(self) -> str:
        return "scoring_mock"

    @property
    def is_available(self) -> bool:
        return True

    async def fetch_ohlcv(
        self, symbol: str, timeframe: Timeframe = Timeframe.H1, since_ms: int | None = None, limit: int = 100
    ) -> list[RawCandle]:
        base_ms = 1700000000000
        mult = 1.0
        if "BTC" in symbol:
            mult = 500.0
        elif "SOL" in symbol:
            mult = 2.0

        return [
            RawCandle(
                timestamp_ms=base_ms + (i * 3600000),
                open=(100.0 + i) * mult,
                high=(106.0 + i) * mult,
                low=(96.0 + i) * mult,
                close=(104.0 + i) * mult,
                volume=120.0 + (i * 10),
            )
            for i in range(60)
        ]

    async def fetch_ticker(self, symbol: str) -> RawTicker | None:
        return None

    async def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_scoring_pipeline_and_api(client: AsyncClient, db_session: AsyncSession):
    """Verify end-to-end scoring pipeline, database persistence, and REST API querying."""
    await seed_default_universe(db_session, exchange_id="binance")

    provider = ScoringMockProvider()

    # 1. Ingest candles
    for sym in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]:
        await ingest_market_ohlcv(
            session=db_session,
            provider=provider,
            symbol=sym,
            market_id=f"binance:{sym}",
            timeframe=Timeframe.H1,
            limit=60,
        )

    # 2. Compute features
    for asset_id in ["BTC", "ETH", "SOL"]:
        await calculate_and_store_asset_features(
            session=db_session,
            asset_id=asset_id,
            timeframe=Timeframe.H1,
            exchange_id="binance",
        )

    # 3. Score single asset
    btc_card = await score_single_asset(
        session=db_session,
        asset_id="BTC",
        timeframe=Timeframe.H1,
    )
    assert btc_card is not None
    assert btc_card.asset_id == "BTC"
    assert btc_card.model_type == "CORE"
    assert 0.0 <= btc_card.opportunity_score <= 100.0

    # 4. Score entire universe
    cards = await score_universe(db_session, timeframe=Timeframe.H1)
    assert len(cards) >= 3

    # Check persistence in database
    db_res = await db_session.execute(select(Score).where(Score.asset_id == "BTC"))
    db_score = db_res.scalar_one_or_none()
    assert db_score is not None
    assert db_score.opportunity_score == btc_card.opportunity_score
    assert "momentum" in db_score.breakdown_json

    # 5. Test API: GET /api/v1/scores
    scores_resp = await client.get("/api/v1/scores")
    assert scores_resp.status_code == 200
    scores_data = scores_resp.json()
    assert len(scores_data) >= 3
    assert "opportunity_score" in scores_data[0]

    # 6. Test API: GET /api/v1/scores/BTC
    detail_resp = await client.get("/api/v1/scores/BTC")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["symbol"] == "BTC"
    assert "components" in detail_data
    assert "momentum" in detail_data["components"]
    assert "explainability_summary" in detail_data

    # 7. Test API: GET /api/v1/scanner
    scanner_resp = await client.get("/api/v1/scanner?min_opportunity=10.0")
    assert scanner_resp.status_code == 200
    scanner_data = scanner_resp.json()
    assert len(scanner_data) >= 3
