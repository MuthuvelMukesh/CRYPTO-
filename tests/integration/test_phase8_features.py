"""Integration tests for Phase 8 Product Features:
- 8.1 Multi-channel Alert Dispatchers & Quiet Hours
- 8.2 Watchlists, custom asset tags, and paper trade journal notes
"""

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import create_app
from src.database.session import get_session_factory


@pytest.fixture
def test_app():
    return create_app()


@pytest.mark.asyncio
async def test_alerts_simulate_and_lifecycle(test_app):
    headers = {"X-API-Key": "dev-api-key-researcher-1"}
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        # 1. Simulate alert
        sim_res = await client.post(
            "/api/v1/alerts/simulate",
            headers=headers,
            json={
                "alert_type": "MOMENTUM_BREAKOUT",
                "severity": "INFO",
                "symbol": "SOL",
                "message": "SOL breakout test signal",
            },
        )
        assert sim_res.status_code == 200
        alert_data = sim_res.json()
        alert_id = alert_data["id"]

        # 2. Mark as read
        patch_res = await client.patch(
            f"/api/v1/alerts/{alert_id}/read",
            headers=headers,
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["is_read"] is True

        # 3. Dismiss / delete alert
        del_res = await client.delete(
            f"/api/v1/alerts/{alert_id}",
            headers=headers,
        )
        assert del_res.status_code == 200
        assert del_res.json()["deleted"] is True


@pytest.mark.asyncio
async def test_watchlists_lifecycle(test_app):
    headers = {"X-API-Key": "dev-api-key-researcher-1"}
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        # 1. Add asset to watchlist
        add_res = await client.post(
            "/api/v1/watchlist",
            headers=headers,
            json={
                "symbol": "SOL",
                "tags": "layer1,high_alpha,accumulating",
                "notes": "Testing watchlist tag persistence",
            },
        )
        assert add_res.status_code == 200
        data = add_res.json()
        assert data["symbol"] == "SOL"
        assert "high_alpha" in data["tags"]

        # 2. List watchlist
        list_res = await client.get("/api/v1/watchlist", headers=headers)
        assert list_res.status_code == 200
        symbols = [item["symbol"] for item in list_res.json()]
        assert "SOL" in symbols

        # 3. Remove asset from watchlist
        del_res = await client.delete("/api/v1/watchlist/SOL", headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["removed"] is True


@pytest.mark.asyncio
async def test_paper_trade_journal(test_app):
    from src.database.models import OHLCV
    from src.utils.time import utc_now

    factory = get_session_factory()
    async with factory() as session:
        now = utc_now()
        session.add(
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

    headers = {"X-API-Key": "dev-api-key-researcher-1"}
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        # 1. Submit paper order
        order_res = await client.post(
            "/api/v1/paper/orders",
            headers=headers,
            json={
                "account_id": "journal_paper",
                "symbol": "BTC",
                "order_type": "MARKET",
                "side": "BUY",
                "quantity": 0.01,
            },
        )
        assert order_res.status_code == 200, order_res.text
        order_id = order_res.json()["id"]

        # 2. Update journal notes and tags
        patch_res = await client.patch(
            f"/api/v1/paper/orders/{order_id}/journal",
            headers=headers,
            json={
                "notes": "Momentum entry after 4h candle close above 20 EMA.",
                "tags": "breakout,trend_following",
            },
        )
        assert patch_res.status_code == 200
        j_data = patch_res.json()
        assert j_data["order_id"] == order_id
        assert "trend_following" in j_data["tags"]

        # 3. Retrieve journal notes
        get_res = await client.get(
            f"/api/v1/paper/orders/{order_id}/journal",
            headers=headers,
        )
        assert get_res.status_code == 200
        assert get_res.json()["notes"] == "Momentum entry after 4h candle close above 20 EMA."


@pytest.mark.asyncio
async def test_backtest_parameter_sweep(test_app):
    """Verify in-sample / out-of-sample hyperparameter grid sweep."""
    headers = {"X-API-Key": "dev-api-key-researcher-1"}
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        sweep_res = await client.post(
            "/api/v1/backtests/sweep",
            headers=headers,
            json={
                "strategy_name": "MomentumBreakout",
                "symbols": ["BTC", "ETH"],
                "train_ratio": 0.7,
                "param_x_name": "stop_loss_pct",
                "param_x_values": [0.05, 0.10],
                "param_y_name": "take_profit_pct",
                "param_y_values": [0.20, 0.30],
                "base_parameters": {"top_n_assets": 2},
            },
        )
        assert sweep_res.status_code == 200, sweep_res.text
        data = sweep_res.json()
        assert data["strategy_name"] == "MomentumBreakout"
        assert len(data["cells"]) == 4
        assert "train_sharpe" in data["cells"][0]
        assert "test_sharpe" in data["cells"][0]
        assert "best_is_params" in data
        assert "best_oos_params" in data
        assert data["data_mode"] == "HISTORICAL"


@pytest.mark.asyncio
async def test_backtest_report_html_export(test_app):
    """Verify reproducible standalone HTML report generation and cost stress table."""
    headers = {"X-API-Key": "dev-api-key-researcher-1"}
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        # Run a backtest synchronously to persist record
        run_res = await client.post(
            "/api/v1/backtests/run",
            headers=headers,
            json={
                "strategy_name": "MomentumBreakout",
                "symbols": ["BTC", "ETH"],
            },
        )
        assert run_res.status_code == 200, run_res.text
        backtest_id = run_res.json()["id"]

        # Request HTML report
        report_res = await client.get(f"/api/v1/backtests/{backtest_id}/report", headers=headers)
        assert report_res.status_code == 200, report_res.text
        assert "text/html" in report_res.headers["content-type"]
        assert "Quantitative Backtest Audit Report" in report_res.text
        assert "Transaction Cost & Slippage Sensitivity Stress Test" in report_res.text
        assert "HISTORICAL DATA" in report_res.text

