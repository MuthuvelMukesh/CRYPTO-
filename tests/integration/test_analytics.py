"""Integration tests for portfolio analytics, correlation matrix, and macro stress testing."""

from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import create_app
from src.database.models import OHLCV
from src.database.session import get_session_factory
from src.utils.time import utc_now


@pytest.fixture
def test_app():
    return create_app()


@pytest.mark.asyncio
async def test_correlation_matrix(test_app):
    """Verify multi-asset correlation calculation without synthetic fabrication."""
    factory = get_session_factory()
    async with factory() as session:
        now = utc_now()

        # Seed 5 hourly candles for BTC and ETH
        for i in range(5):
            t = (now - timedelta(hours=5 - i)).replace(minute=0, second=0, microsecond=0)
            await session.merge(
                OHLCV(
                    time=t,
                    market_id="binance:BTC/USDT",
                    timeframe="1h",
                    open=60000.0 + i * 100,
                    high=60100.0 + i * 100,
                    low=59900.0 + i * 100,
                    close=60050.0 + i * 100,
                    volume=10.0,
                    validation_status="GOOD",
                )
            )
            await session.merge(
                OHLCV(
                    time=t,
                    market_id="binance:ETH/USDT",
                    timeframe="1h",
                    open=3000.0 + i * 10,
                    high=3050.0 + i * 10,
                    low=2950.0 + i * 10,
                    close=3020.0 + i * 10,
                    volume=50.0,
                    validation_status="GOOD",
                )
            )
        await session.commit()

    headers = {"X-API-Key": "dev-api-key-researcher-1"}
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        res = await client.get("/api/v1/analytics/correlation?symbols=BTC,ETH&timeframe=1h&limit=10", headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["data_mode"] == "HISTORICAL"
        assert len(data["symbols"]) == 2
        assert len(data["matrix"]) == 2
        # Check diagonal
        btc_row = next(r for r in data["matrix"] if r["symbol"] == "BTC")
        assert btc_row["correlations"]["BTC"] == 1.0


@pytest.mark.asyncio
async def test_portfolio_stress_and_sector_exposure(test_app):
    """Verify stress test calculations and sector concentration breakdown."""
    factory = get_session_factory()
    now = utc_now()
    async with factory() as session:
        # Seed fresh candle so paper order can execute
        await session.merge(
            OHLCV(
                time=now,
                market_id="binance:BTC/USDT",
                timeframe="1h",
                open=65000.0,
                high=65100.0,
                low=64900.0,
                close=65000.0,
                volume=50.0,
                validation_status="GOOD",
            )
        )
        await session.commit()

    import uuid
    test_acc = f"stress_acc_{uuid.uuid4().hex[:8]}"
    headers = {"X-API-Key": "dev-api-key-researcher-1"}
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        # Place paper order in BTC for account test_acc
        order_res = await client.post(
            "/api/v1/paper/orders",
            headers=headers,
            json={
                "account_id": test_acc,
                "symbol": "BTC",
                "order_type": "MARKET",
                "side": "BUY",
                "quantity": 0.01,
            },
        )
        assert order_res.status_code == 200, order_res.text

        # 1. Test stress scenarios
        stress_res = await client.get(f"/api/v1/analytics/portfolio-stress?account_id={test_acc}", headers=headers)
        assert stress_res.status_code == 200, stress_res.text
        stress_data = stress_res.json()
        assert stress_data["account_id"] == test_acc
        assert stress_data["open_positions_count"] >= 1
        assert len(stress_data["scenarios"]) >= 4

        # In btc_minus_20, drawdown should be negative and reflect BTC drop
        btc_sc = next(s for s in stress_data["scenarios"] if s["scenario_id"] == "btc_minus_20")
        assert btc_sc["drawdown_pct"] < 0
        assert btc_sc["pnl_impact_usd"] < 0
        assert len(btc_sc["position_impacts"]) >= 1

        # 2. Test sector exposure
        sector_res = await client.get(f"/api/v1/analytics/sector-exposure?account_id={test_acc}", headers=headers)
        assert sector_res.status_code == 200, sector_res.text
        sector_data = sector_res.json()
        assert sector_data["account_id"] == test_acc
        assert sector_data["herfindahl_index"] > 0
        assert len(sector_data["sectors"]) >= 1
        assert len(sector_data["risk_contributions"]) >= 1
