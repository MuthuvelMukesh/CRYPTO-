"""Integration tests for Sector Rotation and Alerts REST API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_sectors_api_endpoints(client: AsyncClient) -> None:
    # 1. GET /api/v1/sectors
    res = await client.get("/api/v1/sectors")
    assert res.status_code == 200
    sectors = res.json()
    assert isinstance(sectors, list)
    assert len(sectors) >= 4

    sector_names = [s["sector_name"] for s in sectors]
    assert any(name in sector_names for name in ["Layer 1", "AI & Compute", "DeFi", "Meme"])

    first = sectors[0]
    assert "return_7d" in first
    assert "breadth_pct" in first
    assert "rotation_status" in first

    # 2. GET /api/v1/sectors/{sector_name}
    res_l1 = await client.get(f"/api/v1/sectors/{first['sector_name']}")
    assert res_l1.status_code == 200
    assert res_l1.json()["sector_name"] == first["sector_name"]

    # 3. GET non-existent sector
    res_404 = await client.get("/api/v1/sectors/NonExistentSectorXYZ")
    assert res_404.status_code == 404


@pytest.mark.asyncio
async def test_alerts_api_endpoints(client: AsyncClient) -> None:
    # 1. GET /api/v1/alerts
    res = await client.get("/api/v1/alerts")
    assert res.status_code == 200
    alerts = res.json()
    assert isinstance(alerts, list)
    assert len(alerts) >= 1

    # 2. POST /api/v1/alerts/simulate
    sim_payload = {
        "alert_type": "MOMENTUM_BREAKOUT",
        "severity": "INFO",
        "symbol": "SOL",
        "message": "SOL quantitative breakout test alert.",
        "details": {"test": True},
    }
    res_sim = await client.post("/api/v1/alerts/simulate", json=sim_payload)
    assert res_sim.status_code == 200
    sim_data = res_sim.json()
    assert sim_data["asset_id"] == "SOL"
    assert sim_data["alert_type"] == "MOMENTUM_BREAKOUT"
    assert sim_data["severity"] == "INFO"

    # 3. Verify simulated alert appears in /api/v1/alerts
    res_after = await client.get("/api/v1/alerts?symbol=SOL")
    assert res_after.status_code == 200
    sol_alerts = res_after.json()
    assert any(a["asset_id"] == "SOL" for a in sol_alerts)
