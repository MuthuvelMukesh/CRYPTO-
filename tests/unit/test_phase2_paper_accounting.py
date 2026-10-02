"""Unit tests reproducing Phase 2 defects: symbol collision, risk limits wiring, ledger integrity, and resting orders."""

from decimal import Decimal

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import Settings
from src.database.models import OHLCV, Asset, LedgerEvent, Market, PaperAccount
from src.paper.broker import PaperBroker
from src.paper.models import OrderSubmitRequest, PaperOrderSide, PaperOrderType
from src.paper.reconciliation import reconcile_account_ledger
from src.paper.risk import RiskEngine
from src.utils.exceptions import DuplicateOrderError
from src.utils.time import utc_now


@pytest.mark.asyncio
async def test_symbol_collision_btc_vs_wbtc(db_session: AsyncSession) -> None:
    """Exact price lookup must NOT confuse BTC with WBTC (or ETH with WETH/STETH)."""
    now = utc_now()

    # 1. Create Assets and Markets
    btc_asset = Asset(
        id="BTC", name="Bitcoin", symbol="BTC", asset_class="CORE", primary_sector="Layer 1"
    )
    wbtc_asset = Asset(
        id="WBTC", name="Wrapped BTC", symbol="WBTC", asset_class="CORE", primary_sector="DeFi"
    )
    db_session.add_all([btc_asset, wbtc_asset])
    await db_session.flush()

    btc_market = Market(
        id="binance:BTC/USDT", exchange_id="binance", asset_id="BTC", quote_asset="USDT", symbol="BTC/USDT"
    )
    wbtc_market = Market(
        id="binance:WBTC/USDT", exchange_id="binance", asset_id="WBTC", quote_asset="USDT", symbol="WBTC/USDT"
    )
    db_session.add_all([btc_market, wbtc_market])
    await db_session.flush()

    # 2. Insert OHLCV: WBTC price $50,000, BTC price $65,000
    c_wbtc = OHLCV(
        time=now, market_id="binance:WBTC/USDT", timeframe="1h",
        open=50000.0, high=50100.0, low=49900.0, close=50000.0, volume=10.0, validation_status="GOOD"
    )
    c_btc = OHLCV(
        time=now, market_id="binance:BTC/USDT", timeframe="1h",
        open=65000.0, high=65100.0, low=64900.0, close=65000.0, volume=10.0, validation_status="GOOD"
    )
    # Insert WBTC after BTC to test if ordering/like query grabs WBTC
    db_session.add(c_btc)
    db_session.add(c_wbtc)
    await db_session.commit()

    broker = PaperBroker()

    # Must resolve exactly to BTC (65,000.0), NOT WBTC (50,000.0)
    btc_price = await broker.get_latest_price(db_session, "BTC")
    assert float(btc_price) == 65000.0

    wbtc_price = await broker.get_latest_price(db_session, "WBTC")
    assert float(wbtc_price) == 50000.0


def test_risk_engine_wired_to_settings() -> None:
    """RiskEngine built from Settings must enforce settings values (15%, 12 positions, 15% DD)."""
    custom_settings = Settings(
        MAX_SINGLE_POSITION_PCT=15.0,
        MAX_OPEN_POSITIONS=12,
        MAX_DRAWDOWN_LIMIT_PCT=15.0,
    )
    risk_engine = RiskEngine.from_settings(custom_settings)

    assert risk_engine.max_single_position_pct == 15.0
    assert risk_engine.max_open_positions == 12
    assert risk_engine.max_drawdown_limit_pct == 15.0

    # Test an order of 18% of equity: must FAIL under 15% limit
    total_equity = 100000.0
    val_res = risk_engine.validate_order(
        side=PaperOrderSide.BUY,
        asset_symbol="ETH",
        asset_class="CORE",
        order_value_usd=18000.0,  # 18% of equity
        cash_balance=50000.0,
        total_equity=total_equity,
        open_positions=[],
        current_drawdown_pct=0.0,
    )
    assert val_res.passed is False
    assert "MAX_POSITION_SIZE_EXCEEDED" in val_res.violations


@pytest.mark.asyncio
async def test_idempotency_key_prevents_duplicate_orders(db_session: AsyncSession) -> None:
    """Duplicate order submission with same idempotency key must raise DuplicateOrderError."""
    # Seed BTC candle
    c_btc = OHLCV(
        time=utc_now(), market_id="binance:BTC/USDT", timeframe="1h",
        open=60000.0, high=60100.0, low=59900.0, close=60000.0, volume=10.0, validation_status="GOOD"
    )
    db_session.add(c_btc)
    await db_session.commit()

    broker = PaperBroker()
    account_id = "test_idempotency"
    await broker.get_or_create_account(db_session, account_id=account_id, starting_balance=100000.0)

    key = "unique-order-uuid-12345"
    req = OrderSubmitRequest(
        account_id=account_id,
        symbol="BTC",
        side=PaperOrderSide.BUY,
        quantity=0.1,
        idempotency_key=key,
    )

    # First submission succeeds
    res1 = await broker.submit_order(db_session, req)
    assert res1.status == "FILLED"

    # Second submission with same key must raise DuplicateOrderError
    with pytest.raises(DuplicateOrderError):
        await broker.submit_order(db_session, req)


@pytest.mark.asyncio
async def test_ledger_append_only_immutability(db_session: AsyncSession) -> None:
    """LedgerEvent must be immutable: updating or deleting a row must raise an error."""
    ev = LedgerEvent(
        event_type="ACCOUNT_CREATED",
        account_id="acc_immutability",
        amount_usd=Decimal("100000.0"),
        cash_balance_after=Decimal("100000.0"),
        data_mode="LIVE",
    )
    db_session.add(ev)
    await db_session.commit()

    ev_id = ev.id

    # Attempting to update ledger row must fail
    with pytest.raises(ValueError):
        await db_session.execute(
            update(LedgerEvent).where(LedgerEvent.id == ev_id).values(amount_usd=Decimal("999999.0"))
        )
        await db_session.commit()

    await db_session.rollback()

    # Attempting to delete ledger row must fail
    with pytest.raises(ValueError):
        await db_session.execute(
            delete(LedgerEvent).where(LedgerEvent.id == ev_id)
        )
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_ledger_reconciliation_detects_tampering(db_session: AsyncSession) -> None:
    """Reconciliation replays ledger and detects discrepancies against accounts/positions."""
    # Seed BTC candle
    c_btc = OHLCV(
        time=utc_now(), market_id="binance:BTC/USDT", timeframe="1h",
        open=60000.0, high=60100.0, low=59900.0, close=60000.0, volume=10.0, validation_status="GOOD"
    )
    db_session.add(c_btc)
    await db_session.commit()

    broker = PaperBroker()
    account_id = "acc_reconcile"
    await broker.get_or_create_account(db_session, account_id=account_id, starting_balance=100000.0)

    # Buy BTC (0.2 BTC = $12,000 <= 15% limit of $100,000)
    await broker.submit_order(
        db_session,
        OrderSubmitRequest(account_id=account_id, symbol="BTC", side=PaperOrderSide.BUY, quantity=0.2),
    )

    # 1. Untampered reconciliation must pass
    rec_pass = await reconcile_account_ledger(db_session, account_id=account_id)
    assert rec_pass.passed is True
    assert rec_pass.discrepancy_count == 0

    # 2. Tamper account cash balance
    account = (await db_session.execute(select(PaperAccount).where(PaperAccount.id == account_id))).scalar_one()
    account.cash_balance = Decimal("999999.0")  # Fraudulent cash
    await db_session.commit()

    # Reconciliation must catch the cash mismatch!
    rec_fail = await reconcile_account_ledger(db_session, account_id=account_id)
    assert rec_fail.passed is False
    assert rec_fail.discrepancy_count > 0
    assert any("Cash mismatch" in d for d in rec_fail.discrepancies)


@pytest.mark.asyncio
async def test_resting_limit_orders_execute_only_when_crossed(db_session: AsyncSession) -> None:
    """Resting limit orders must stay OPEN until a candle crosses limit price."""
    now = utc_now()
    # 1. Seed initial BTC candle at 60,000
    c_init = OHLCV(
        time=now, market_id="binance:BTC/USDT", timeframe="1h",
        open=60000.0, high=60500.0, low=59500.0, close=60000.0, volume=10.0, validation_status="GOOD"
    )
    db_session.add(c_init)
    await db_session.commit()

    broker = PaperBroker()
    account_id = "acc_resting_orders"
    await broker.get_or_create_account(db_session, account_id=account_id, starting_balance=100000.0)

    # 2. Place limit buy at 55,000 (0.2 BTC = $11,000 <= 15% limit)
    req = OrderSubmitRequest(
        account_id=account_id,
        symbol="BTC",
        side=PaperOrderSide.BUY,
        order_type=PaperOrderType.LIMIT,
        quantity=0.2,
        limit_price=55000.0,
    )
    order_res = await broker.submit_order(db_session, req)
    assert order_res.status == "OPEN"
    assert len(order_res.fills) == 0

    # 3. Bar arrives with low=56,000 (does NOT cross 55,000 limit)
    candle_no_cross = OHLCV(
        time=now, market_id="binance:BTC/USDT", timeframe="1h",
        open=59000.0, high=59500.0, low=56000.0, close=57000.0, volume=10.0, validation_status="GOOD"
    )
    filled_none = await broker.evaluate_resting_orders(db_session, candle_no_cross)
    assert len(filled_none) == 0

    # 4. Bar arrives with low=54,000 (CROSSES 55,000 limit)
    candle_cross = OHLCV(
        time=now, market_id="binance:BTC/USDT", timeframe="1h",
        open=56000.0, high=56500.0, low=54000.0, close=55000.0, volume=10.0, validation_status="GOOD"
    )
    filled = await broker.evaluate_resting_orders(db_session, candle_cross)
    assert len(filled) == 1
    assert filled[0].status == "FILLED"

    # Verify position is now open and cash deducted
    summary = await broker.get_portfolio_summary(db_session, account_id=account_id)
    assert summary.open_positions_count == 1
    assert summary.open_positions[0].symbol == "BTC"
    assert summary.cash_balance < 100000.0

