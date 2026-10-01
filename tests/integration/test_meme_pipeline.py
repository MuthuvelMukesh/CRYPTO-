from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient

from src.scoring.meme_radar import MemeAuditRecord


@pytest.mark.asyncio
async def test_meme_radar_api_endpoints(client: AsyncClient) -> None:
    mock_records = [
        MemeAuditRecord(
            symbol="DOGE", name="Dogecoin", chain_id="bsc", dex_id="pancakeswap",
            pair_address="doge_pair_1", price_usd=0.12, liquidity_usd=5000000.0,
            volume_24h_usd=25000000.0, volume_acceleration_1h=1.2, volume_acceleration_5m=1.0,
            buy_pressure_ratio=0.55, pair_age_hours=500.0, top_10_holders_pct=25.0, holder_count=50000,
            liquidity_score=80.0, volume_momentum_score=75.0, buy_pressure_score=60.0,
            holder_distribution_score=85.0, gross_score=75.0, total_penalties=0.0,
            opportunity_score=75.0, risk_level="LOW", risk_flags=[],
        ),
        MemeAuditRecord(
            symbol="PEPE", name="Pepe", chain_id="ethereum", dex_id="uniswap_v3",
            pair_address="pepe_pair_1", price_usd=0.00001, liquidity_usd=15000000.0,
            volume_24h_usd=40000000.0, volume_acceleration_1h=2.0, volume_acceleration_5m=1.5,
            buy_pressure_ratio=0.65, pair_age_hours=1200.0, top_10_holders_pct=15.0, holder_count=120000,
            liquidity_score=90.0, volume_momentum_score=85.0, buy_pressure_score=70.0,
            holder_distribution_score=80.0, gross_score=81.0, total_penalties=0.0,
            opportunity_score=81.0, risk_level="LOW", risk_flags=[],
        ),
        MemeAuditRecord(
            symbol="SHIB", name="Shiba Inu", chain_id="ethereum", dex_id="uniswap_v2",
            pair_address="shib_pair_1", price_usd=0.00002, liquidity_usd=8000000.0,
            volume_24h_usd=18000000.0, volume_acceleration_1h=0.9, volume_acceleration_5m=0.8,
            buy_pressure_ratio=0.48, pair_age_hours=3000.0, top_10_holders_pct=30.0, holder_count=80000,
            liquidity_score=70.0, volume_momentum_score=50.0, buy_pressure_score=48.0,
            holder_distribution_score=70.0, gross_score=59.0, total_penalties=5.0,
            opportunity_score=54.0, risk_level="MODERATE", risk_flags=[],
        ),
    ]

    with patch("apps.api.routes.meme.radar_engine.scan_meme_tokens", new=AsyncMock(side_effect=lambda symbols=None: [r for r in mock_records if not symbols or r.symbol in symbols])):
        # 1. GET /api/v1/meme/radar
        res = await client.get("/api/v1/meme/radar")
        assert res.status_code == 200
        records = res.json()
        assert isinstance(records, list)
        assert len(records) >= 3

        symbols = {r["symbol"] for r in records}
        assert "DOGE" in symbols or "PEPE" in symbols

        first = records[0]
        assert "opportunity_score" in first
        assert "liquidity_usd" in first
        assert "buy_pressure_ratio" in first
        assert "risk_flags" in first

        # 2. GET /api/v1/meme/radar with score filter
        res_filtered = await client.get("/api/v1/meme/radar?min_score=50.0")
        assert res_filtered.status_code == 200
        for r in res_filtered.json():
            assert r["opportunity_score"] >= 50.0

        # 3. GET /api/v1/meme/{symbol} detail
        res_doge = await client.get("/api/v1/meme/DOGE")
        assert res_doge.status_code == 200
        doge_data = res_doge.json()
        assert doge_data["symbol"] == "DOGE"
        assert doge_data["liquidity_usd"] > 0.0
