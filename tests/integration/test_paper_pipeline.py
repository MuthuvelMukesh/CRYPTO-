"""Integration tests for paper trading REST API endpoints, order routing, and risk rejections."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.pipeline import seed_default_universe


@pytest.mark.asyncio
async def test_paper_trading_api_endpoints_and_risk(client: AsyncClient, db_session: AsyncSession) -> None:
    await seed_default_universe(db_session, exchange_id="binance")

    from src.database.models import OHLCV
    from src.utils.time import utc_now
    now = utc_now()
    db_session.add_all([
        OHLCV(time=now, market_id="binance:BTC/USDT", timeframe="1h", open=60000.0, high=60100.0, low=59900.0, close=60000.0, volume=100.0, validation_status="GOOD"),
        OHLCV(time=now, market_id="binance:DOGE/USDT", timeframe="1h", open=0.125, high=0.13, low=0.12, close=0.125, volume=10000.0, validation_status="GOOD"),
    ])
    await db_session.commit()

    # 1. GET /api/v1/paper/account
    res_acc = await client.get("/api/v1/paper/account?account_id=api_test")
    assert res_acc.status_code == 200
    acc_data = res_acc.json()
    assert acc_data["account_id"] == "api_test"
    assert acc_data["starting_balance"] == 100000.0
    assert acc_data["cash_balance"] == 100000.0
    assert acc_data["open_positions_count"] == 0

    # 2. POST /api/v1/paper/orders: Valid Buy Order (0.1 BTC)
    buy_payload = {
        "account_id": "api_test",
        "symbol": "BTC",
        "side": "BUY",
        "order_type": "MARKET",
        "quantity": 0.1,
    }
    res_order = await client.post("/api/v1/paper/orders", json=buy_payload)
    assert res_order.status_code == 200, res_order.text
    order_data = res_order.json()
    assert order_data["status"] == "FILLED"
    assert order_data["symbol"] == "BTC"
    assert len(order_data["fills"]) == 1

    # 3. GET /api/v1/paper/positions: Verify open BTC position
    res_pos = await client.get("/api/v1/paper/positions?account_id=api_test")
    assert res_pos.status_code == 200
    pos_list = res_pos.json()
    assert len(pos_list) == 1
    assert pos_list[0]["symbol"] == "BTC"
    assert pos_list[0]["quantity"] == 0.1

    # 4. POST /api/v1/paper/orders: Risk Rejection (Exceeding 5% Meme quota)
    # Price of DOGE is ~$0.125 -> 100,000 DOGE = $12,500 (12.5% of $100k equity) -> MUST BE REJECTED!
    excess_meme_payload = {
        "account_id": "api_test",
        "symbol": "DOGE",
        "side": "BUY",
        "order_type": "MARKET",
        "quantity": 100000.0,
    }
    res_reject = await client.post("/api/v1/paper/orders", json=excess_meme_payload)
    assert res_reject.status_code == 400
    assert "Meme exposure limit" in res_reject.json()["detail"]

    # 5. POST /api/v1/paper/positions/BTC/close: Liquidate position
    res_close = await client.post("/api/v1/paper/positions/BTC/close?account_id=api_test")
    assert res_close.status_code == 200
    close_data = res_close.json()
    assert close_data["is_open"] is False

    # 6. Verify positions count is now 0
    res_pos_after = await client.get("/api/v1/paper/positions?account_id=api_test")
    assert len(res_pos_after.json()) == 0

    # 7. POST /api/v1/paper/reset: Reset account
    res_reset = await client.post(
        "/api/v1/paper/reset",
        json={"account_id": "api_test", "starting_balance": 100000.0},
    )
    assert res_reset.status_code == 200
    assert res_reset.json()["status"] == "SUCCESS"
