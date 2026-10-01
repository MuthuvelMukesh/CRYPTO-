"""Unit tests for virtual paper broker order execution and portfolio accounting."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import OHLCV
from src.ingestion.pipeline import seed_default_universe
from src.paper.broker import PaperBroker
from src.paper.models import OrderSubmitRequest, PaperOrderSide, PaperOrderType
from src.utils.time import utc_now


async def _seed_candle(session: AsyncSession, market_id: str, close: float) -> None:
    c = OHLCV(
        time=utc_now(),
        market_id=market_id,
        timeframe="1h",
        open=close,
        high=close * 1.01,
        low=close * 0.99,
        close=close,
        volume=100.0,
        validation_status="GOOD",
    )
    session.add(c)
    await session.commit()


@pytest.mark.asyncio
async def test_paper_account_lifecycle_and_buy_order(db_session: AsyncSession) -> None:
    await seed_default_universe(db_session, exchange_id="binance")
    await _seed_candle(db_session, "binance:BTC/USDT", 60000.0)
    broker = PaperBroker()

    # 1. Initialize account
    account = await broker.get_or_create_account(db_session, account_id="test_acc", starting_balance=100000.0)
    assert account.id == "test_acc"
    assert account.cash_balance == 100000.0

    # 2. Submit Buy Order for 0.1 BTC
    order_req = OrderSubmitRequest(
        account_id="test_acc",
        symbol="BTC",
        side=PaperOrderSide.BUY,
        order_type=PaperOrderType.MARKET,
        quantity=0.1,
    )
    order_res = await broker.submit_order(db_session, order_req)
    assert order_res.status == "FILLED"
    assert len(order_res.fills) == 1
    fill = order_res.fills[0]
    assert fill.fill_price > 0.0
    assert fill.fee_usd > 0.0

    # 3. Cash balance must be deducted
    summary = await broker.get_portfolio_summary(db_session, account_id="test_acc")
    assert summary.cash_balance < 100000.0
    assert summary.open_positions_count == 1
    btc_pos = summary.open_positions[0]
    assert btc_pos.symbol == "BTC"
    assert pytest.approx(btc_pos.quantity, rel=1e-4) == 0.1


@pytest.mark.asyncio
async def test_multiple_buys_and_averaging_entry_price(db_session: AsyncSession) -> None:
    await seed_default_universe(db_session, exchange_id="binance")
    await _seed_candle(db_session, "binance:SOL/USDT", 150.0)
    broker = PaperBroker()
    account_id = "test_avg"
    await broker.get_or_create_account(db_session, account_id=account_id, starting_balance=50000.0)

    # Buy 10 SOL
    await broker.submit_order(
        db_session,
        OrderSubmitRequest(account_id=account_id, symbol="SOL", side=PaperOrderSide.BUY, quantity=10.0),
    )
    # Buy another 10 SOL
    await broker.submit_order(
        db_session,
        OrderSubmitRequest(account_id=account_id, symbol="SOL", side=PaperOrderSide.BUY, quantity=10.0),
    )

    summary = await broker.get_portfolio_summary(db_session, account_id=account_id)
    assert summary.open_positions_count == 1
    sol_pos = summary.open_positions[0]
    assert pytest.approx(sol_pos.quantity, rel=1e-4) == 20.0
    assert sol_pos.avg_entry_price > 0.0


@pytest.mark.asyncio
async def test_sell_order_and_realized_pnl(db_session: AsyncSession) -> None:
    await seed_default_universe(db_session, exchange_id="binance")
    await _seed_candle(db_session, "binance:ETH/USDT", 3000.0)
    broker = PaperBroker()
    account_id = "test_sell"
    await broker.get_or_create_account(db_session, account_id=account_id, starting_balance=100000.0)

    # 1. Buy 1.0 ETH
    await broker.submit_order(
        db_session,
        OrderSubmitRequest(account_id=account_id, symbol="ETH", side=PaperOrderSide.BUY, quantity=1.0),
    )

    # 2. Sell 0.5 ETH (partial sell)
    sell_res = await broker.submit_order(
        db_session,
        OrderSubmitRequest(account_id=account_id, symbol="ETH", side=PaperOrderSide.SELL, quantity=0.5),
    )
    assert sell_res.status == "FILLED"

    summary = await broker.get_portfolio_summary(db_session, account_id=account_id)
    assert summary.open_positions_count == 1
    eth_pos = summary.open_positions[0]
    assert pytest.approx(eth_pos.quantity, rel=1e-4) == 0.5
    assert isinstance(eth_pos.realized_pnl, float)

    # 3. Liquidate remaining ETH via close_position
    close_pos = await broker.close_position(db_session, account_id=account_id, symbol="ETH")
    assert close_pos.is_open is False
    assert close_pos.quantity == 0.0

    summary_final = await broker.get_portfolio_summary(db_session, account_id=account_id)
    assert summary_final.open_positions_count == 0


@pytest.mark.asyncio
async def test_account_reset(db_session: AsyncSession) -> None:
    await seed_default_universe(db_session, exchange_id="binance")
    await _seed_candle(db_session, "binance:SOL/USDT", 150.0)
    broker = PaperBroker()
    account_id = "test_reset"
    await broker.get_or_create_account(db_session, account_id=account_id, starting_balance=100000.0)

    # Buy SOL
    await broker.submit_order(
        db_session,
        OrderSubmitRequest(account_id=account_id, symbol="SOL", side=PaperOrderSide.BUY, quantity=5.0),
    )

    # Reset account
    reset_acc = await broker.reset_account(db_session, account_id=account_id, starting_balance=100000.0)
    assert reset_acc.cash_balance == 100000.0

    summary = await broker.get_portfolio_summary(db_session, account_id=account_id)
    assert summary.open_positions_count == 0
    assert summary.cash_balance == 100000.0
