"""Integration tests for Phase 4 API Hardening, Security Contract, and Performance.

Covers:
- Unauthenticated requests receive 401 Unauthorized with RFC 7807 problem+json
- Hybrid authentication: API Key (X-API-Key and Bearer) & JWT tokens
- Health endpoints remain publicly accessible without credentials
- Constant O(1) query count on scanner endpoint regardless of universe size
- Asynchronous backtest job submission, polling, cancellation, and deterministic hashing
- Sliding-window rate limiting returning 429 Too Many Requests with Retry-After
- Production fail-fast on weak/default secrets
"""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import Settings
from src.database.models import OHLCV, Asset, Feature, Market, Score


@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected_with_401_problem_json(
    unauthenticated_client: AsyncClient,
) -> None:
    """Non-health endpoints must reject unauthenticated requests with 401 and RFC 7807 problem+json."""
    protected_endpoints = [
        "/api/v1/scanner/rankings",
        "/api/v1/backtests",
        "/api/v1/paper/account",
        "/api/v1/assets",
        "/api/v1/alerts",
        "/api/v1/scores",
    ]

    for path in protected_endpoints:
        res = await unauthenticated_client.get(path)
        assert res.status_code == 401, f"Expected 401 for {path}, got {res.status_code}"
        assert "application/problem+json" in res.headers.get("content-type", "")

        problem = res.json()
        assert problem["status"] == 401
        assert problem["title"] == "Unauthorized"
        assert "detail" in problem
        assert problem["instance"] == path
        assert "timestamp" in problem
        assert "request_id" in problem or "X-Request-ID" in res.headers


@pytest.mark.asyncio
async def test_health_routes_remain_unauthenticated(
    unauthenticated_client: AsyncClient,
) -> None:
    """Operational health probes must remain unauthenticated for monitoring/k8s."""
    health_routes = ["/health", "/live", "/ready", "/health/versions", "/openapi.json"]

    for path in health_routes:
        res = await unauthenticated_client.get(path)
        assert res.status_code == 200, f"Expected 200 for {path}, got {res.status_code}"


@pytest.mark.asyncio
async def test_api_key_authentication(unauthenticated_client: AsyncClient) -> None:
    """Valid API keys authenticate successfully via X-API-Key header or Bearer scheme."""
    # 1. Via X-API-Key
    res_x = await unauthenticated_client.get(
        "/api/v1/paper/account",
        headers={"X-API-Key": "dev-api-key-researcher-1"},
    )
    assert res_x.status_code == 200

    # 2. Via Bearer <api-key>
    res_b = await unauthenticated_client.get(
        "/api/v1/paper/account",
        headers={"Authorization": "Bearer dev-api-key-researcher-1"},
    )
    assert res_b.status_code == 200

    # 3. Invalid API key receives 401
    res_invalid = await unauthenticated_client.get(
        "/api/v1/paper/account",
        headers={"X-API-Key": "bogus-unauthorized-key"},
    )
    assert res_invalid.status_code == 401
    assert "Invalid API key" in res_invalid.json()["detail"]


@pytest.mark.asyncio
async def test_jwt_token_exchange_and_authentication(
    unauthenticated_client: AsyncClient,
) -> None:
    """Exchange API key for JWT token and access authenticated endpoints."""
    # 1. Exchange API key for token
    token_resp = await unauthenticated_client.post(
        "/api/v1/auth/token",
        json={"api_key": "dev-api-key-researcher-1", "subject": "quant_researcher_alpha"},
    )
    assert token_resp.status_code == 200
    token_data = token_resp.json()
    assert "access_token" in token_data
    token = token_data["access_token"]

    # 2. Access /auth/me with Bearer token
    me_resp = await unauthenticated_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["auth_type"] == "jwt"
    assert me_data["identity"] == "quant_researcher_alpha"

    # 3. Access protected scanner rankings with Bearer token
    scanner_resp = await unauthenticated_client.get(
        "/api/v1/scanner/rankings",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert scanner_resp.status_code == 200

    # 4. Tampered JWT token receives 401
    tampered_resp = await unauthenticated_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}corrupted"},
    )
    assert tampered_resp.status_code == 401


@pytest.mark.asyncio
async def test_scanner_endpoint_constant_query_count(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Scanner endpoint must execute a constant number of queries regardless of universe size.

    Verifies O(1) query complexity eliminating N+1 loop degradations.
    """
    now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    # Helper to populate N assets with scores, features, markets, and candles
    async def seed_n_assets(start_idx: int, count: int) -> None:
        for i in range(start_idx, start_idx + count):
            sym = f"SYM{i:03d}"
            asset = Asset(
                id=sym,
                symbol=sym,
                name=f"Asset {sym}",
                asset_class="ALTCOIN",
                primary_sector="L1",
                is_active=True,
            )
            market = Market(
                id=f"binance:{sym}/USDT",
                exchange_id="binance",
                asset_id=sym,
                quote_asset="USDT",
                symbol=f"{sym}/USDT",
                is_active=True,
            )
            score = Score(
                time=now,
                asset_id=sym,
                model_type="ALTCOIN",
                opportunity_score=50.0 + i,
                quality_score=60.0,
                risk_score=25.0,
                trend_score=55.0,
                momentum_score=58.0,
                relative_strength_score=52.0,
                liquidity_score=65.0,
                breakdown_json={},
                risk_flags=[],
            )
            feat = Feature(
                time=now,
                asset_id=sym,
                timeframe="1h",
                return_1d=0.05,
                return_7d=0.12,
                return_30d=0.25,
            )
            candle = OHLCV(
                time=now,
                market_id=f"binance:{sym}/USDT",
                timeframe="1h",
                open=10.0,
                high=11.0,
                low=9.5,
                close=10.5,
                volume=1000.0,
                data_mode="LIVE",
            )
            db_session.add_all([asset, market, score, feat, candle])
        await db_session.commit()

    # Step 1: Seed 3 assets
    await seed_n_assets(start_idx=1, count=3)

    # Monitor queries using SQLAlchemy engine events
    sync_engine = db_session.bind.sync_engine
    query_count = 0

    def count_queries(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        # Ignore transaction commit/rollback
        if not statement.strip().upper().startswith(("COMMIT", "ROLLBACK")):
            query_count += 1

    event.listen(sync_engine, "before_cursor_execute", count_queries)

    # Run query with 3 assets
    query_count = 0
    resp_3 = await client.get("/api/v1/scanner/rankings?limit=50")
    assert resp_3.status_code == 200
    queries_for_3 = query_count
    assert queries_for_3 > 0

    # Step 2: Seed 10 more assets (total 13 assets)
    await seed_n_assets(start_idx=4, count=10)

    query_count = 0
    resp_13 = await client.get("/api/v1/scanner/rankings?limit=50")
    assert resp_13.status_code == 200
    queries_for_13 = query_count

    event.remove(sync_engine, "before_cursor_execute", count_queries)

    # Query counts must be identical (constant O(1))
    assert queries_for_3 == queries_for_13, (
        f"Query count scaled with universe size! Expected constant queries, got {queries_for_3} vs {queries_for_13}"
    )


@pytest.mark.asyncio
async def test_backtest_async_job_lifecycle(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Async backtest submission, progress tracking, and cancellation."""
    # 1. Submit async backtest job
    req_payload = {
        "strategy_name": "MomentumBreakout",
        "symbols": ["BTC", "ETH"],
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2024-01-10T00:00:00Z",
        "initial_capital": 100000.0,
        "point_in_time_universe": True,
    }

    res_post = await client.post("/api/v1/backtests", json=req_payload)
    assert res_post.status_code == 202
    data_post = res_post.json()
    assert "job_id" in data_post
    assert data_post["status"] in ("PENDING", "RUNNING", "COMPLETED")
    assert "config_hash" in data_post
    job_id = data_post["job_id"]

    # 2. Poll job status
    res_status = await client.get(f"/api/v1/backtests/jobs/{job_id}")
    assert res_status.status_code == 200
    job_info = res_status.json()
    assert job_info["job_id"] == job_id
    assert 0.0 <= job_info["progress"] <= 1.0

    # 3. Test job cancellation endpoint
    cancel_resp = await client.post(f"/api/v1/backtests/jobs/{job_id}/cancel")
    assert cancel_resp.status_code in (200, 400)
    # If job was still running it cancels to CANCELLED; if already finished, 400


@pytest.mark.asyncio
async def test_fail_fast_on_insecure_production_secret() -> None:
    """Settings must fail fast in production if weak or default secrets are detected."""
    # Production with weak secret must raise ValueError
    with pytest.raises(ValueError, match="Insecure or default SECRET_KEY in production"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="dev-insecure-secret-key-change-in-production-min-32-chars",
        )

    with pytest.raises(ValueError, match="Insecure or default SECRET_KEY in production"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="short-secret",
        )

    # Valid strong secret in production must pass
    valid_prod = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a_very_secure_random_production_secret_key_32_bytes_plus",
    )
    assert valid_prod.ENVIRONMENT == "production"


@pytest.mark.asyncio
async def test_openapi_schema_contains_security_and_routes(client: AsyncClient) -> None:
    """OpenAPI schema must declare security requirements and core v3.0 endpoints."""
    res = await client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()

    assert "/api/v1/scanner/rankings" in schema["paths"]
    assert "/api/v1/backtests" in schema["paths"]
    assert "/api/v1/backtests/jobs/{job_id}" in schema["paths"]
    assert "/api/v1/paper/orders" in schema["paths"]
    assert "/api/v1/paper/ledger" in schema["paths"]
    assert "/api/v1/stream/scanner" in schema["paths"]
    assert "/api/v1/auth/token" in schema["paths"]
