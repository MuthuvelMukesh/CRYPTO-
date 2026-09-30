"""Integration tests for Meme Coin Radar REST APIs and on-chain intelligence."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_meme_radar_api_endpoints(client: AsyncClient) -> None:
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
