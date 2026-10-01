"""Integration tests for FastAPI health and diagnostics endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    """Verify GET /health returns 200 and valid schema."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"].upper() in ["UP", "DOWN", "DEGRADED", "HEALTHY"]
    assert "app" in data
    assert "version" in data
    assert "components" in data
    assert "database" in data["components"]
    assert data["components"]["database"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_ready_and_live_probes(client: AsyncClient):
    """Verify Kubernetes readiness and liveness probes."""
    live_res = await client.get("/live")
    assert live_res.status_code == 200
    assert live_res.json().get("live") is True

    ready_res = await client.get("/ready")
    assert ready_res.status_code == 200
    assert ready_res.json() == {"ready": True}


@pytest.mark.asyncio
async def test_openapi_schema(client: AsyncClient):
    """Verify OpenAPI documentation schema generation."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert "openapi" in spec
    assert "/health" in spec["paths"]
    assert "/ready" in spec["paths"]
    assert "/live" in spec["paths"]
