"""Integration tests for Asset detail, historical OHLCV, and quantitative features API."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import OHLCV, Asset, Feature, Market


@pytest.mark.asyncio
async def test_get_asset_detail_and_ohlcv(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test retrieving asset metadata and historical OHLCV candlestick series."""
    asset = Asset(
        id="asset-sol",
        name="Solana",
        symbol="SOL",
        asset_class="ALTCOIN",
        primary_sector="L1",
        is_active=True,
    )
    db_session.add(asset)

    market = Market(
        id="binance:SOL/USDT",
        exchange_id="binance",
        asset_id=asset.id,
        symbol="SOL/USDT",
        quote_asset="USDT",
        is_active=True,
    )
    db_session.add(market)

    # Add candles
    now = datetime.now(UTC)
    c1 = OHLCV(
        time=now,
        market_id=market.id,
        timeframe="1h",
        open=140.0,
        high=145.0,
        low=139.0,
        close=143.5,
        volume=250000.0,
        validation_status="VALID",
    )
    db_session.add(c1)
    await db_session.commit()

    # 1. Query asset detail
    res = await client.get("/api/v1/assets/SOL")
    assert res.status_code == 200
    data = res.json()
    assert data["symbol"] == "SOL"
    assert data["primary_sector"] == "L1"

    # 2. Query OHLCV
    ohlcv_res = await client.get("/api/v1/ohlcv/SOL?timeframe=1h")
    assert ohlcv_res.status_code == 200
    candles = ohlcv_res.json()
    assert len(candles) >= 1
    assert candles[-1]["close"] == 143.5

    # 3. Query unknown asset returns 404
    err_res = await client.get("/api/v1/assets/UNKNOWNTOKEN")
    assert err_res.status_code == 404


@pytest.mark.asyncio
async def test_get_asset_features(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test retrieving latest quantitative feature vector for an asset."""
    asset = Asset(
        id="asset-avax",
        name="Avalanche",
        symbol="AVAX",
        asset_class="ALTCOIN",
        primary_sector="L1",
        is_active=True,
    )
    db_session.add(asset)

    now = datetime.now(UTC)
    feat = Feature(
        time=now,
        asset_id=asset.id,
        timeframe="1h",
        return_1d=0.045,
        return_7d=0.12,
        return_30d=0.28,
        momentum_acceleration=0.015,
        rs_btc_30d=0.08,
        ema20_ratio=1.03,
        ema50_ratio=1.06,
        adx_14=32.5,
        atr_14_pct=0.042,
        volume_to_20d_avg=1.45,
        spread_est_bps=12.5,
        realized_vol_30d=0.55,
    )
    db_session.add(feat)
    await db_session.commit()

    # Retrieve features
    res = await client.get("/api/v1/assets/AVAX/features?timeframe=1h")
    assert res.status_code == 200
    data = res.json()
    assert data["symbol"] == "AVAX"
    assert data["return_1d"] == 0.045
    assert data["adx_14"] == 32.5
    assert data["spread_est_bps"] == 12.5

    # Missing features returns 404
    missing_res = await client.get("/api/v1/assets/UNKNOWNTOKEN/features")
    assert missing_res.status_code == 404
