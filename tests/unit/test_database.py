"""Unit tests for database models, queries, and health checks."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Asset, Exchange, Market, PaperAccount
from src.database.session import check_db_health


@pytest.mark.asyncio
async def test_database_health_check():
    """Verify check_db_health returns healthy status."""
    health = await check_db_health()
    assert health["status"] == "healthy"
    assert "latency_ms" in health
    assert "dialect" in health


@pytest.mark.asyncio
async def test_asset_and_market_crud(db_session: AsyncSession):
    """Test asset, exchange, and market creation and retrieval."""
    # Create Asset
    btc = Asset(
        id="BTC",
        name="Bitcoin",
        symbol="BTC",
        asset_class="CORE",
        primary_sector="Store of Value",
        is_active=True,
    )
    db_session.add(btc)

    # Create Exchange
    binance = Exchange(
        id="binance",
        name="Binance",
        is_dex=False,
        is_active=True,
    )
    db_session.add(binance)
    await db_session.flush()

    # Create Market
    market = Market(
        id="binance:BTC/USDT",
        exchange_id="binance",
        asset_id="BTC",
        quote_asset="USDT",
        symbol="BTC/USDT",
        is_active=True,
    )
    db_session.add(market)
    await db_session.commit()

    # Query back
    result = await db_session.execute(select(Asset).where(Asset.id == "BTC"))
    queried_btc = result.scalar_one_or_none()
    assert queried_btc is not None
    assert queried_btc.symbol == "BTC"
    assert queried_btc.asset_class == "CORE"


@pytest.mark.asyncio
async def test_paper_account_creation(db_session: AsyncSession):
    """Test paper trading account insertion and defaults."""
    account = PaperAccount(
        id="paper_main",
        name="Main Paper Account",
        base_currency="USD",
        starting_balance=100000.0,
        cash_balance=100000.0,
    )
    db_session.add(account)
    await db_session.commit()

    result = await db_session.execute(select(PaperAccount).where(PaperAccount.id == "paper_main"))
    acc = result.scalar_one_or_none()
    assert acc is not None
    assert acc.cash_balance == 100000.0
