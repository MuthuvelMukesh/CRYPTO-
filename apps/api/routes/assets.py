"""Asset catalog and historical market data query endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.deps import get_db
from src.config.constants import AssetClass, Timeframe
from src.database.models import OHLCV, Asset

router = APIRouter(prefix="/api/v1", tags=["Assets & Market Data"])


class MarketResponse(BaseModel):
    id: str
    exchange_id: str
    symbol: str
    quote_asset: str
    is_active: bool


class AssetResponse(BaseModel):
    id: str
    name: str
    symbol: str
    asset_class: str
    primary_sector: str
    is_active: bool
    markets: list[MarketResponse] = Field(default_factory=list)


class CandleResponse(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    validation_status: str


@router.get("/assets", response_model=list[AssetResponse], summary="List all monitored cryptocurrency assets")
async def list_assets(
    asset_class: AssetClass | None = Query(None, description="Filter by asset class (CORE, ALTCOIN, MEME)"),
    sector: str | None = Query(None, description="Filter by primary sector"),
    is_active: bool = Query(True, description="Filter active assets"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve catalog of cryptocurrency assets registered in platform universe."""
    query = (
        select(Asset)
        .options(selectinload(Asset.markets))
        .where(Asset.is_active == is_active)
        .order_by(Asset.symbol)
        .offset(offset)
        .limit(limit)
    )

    if asset_class:
        query = query.where(Asset.asset_class == asset_class.value)
    if sector:
        query = query.where(Asset.primary_sector == sector)

    res = await db.execute(query)
    assets = res.scalars().all()

    return [
        AssetResponse(
            id=a.id,
            name=a.name,
            symbol=a.symbol,
            asset_class=a.asset_class,
            primary_sector=a.primary_sector,
            is_active=a.is_active,
            markets=[
                MarketResponse(
                    id=m.id,
                    exchange_id=m.exchange_id,
                    symbol=m.symbol,
                    quote_asset=m.quote_asset,
                    is_active=m.is_active,
                )
                for m in a.markets
            ],
        )
        for a in assets
    ]


@router.get("/assets/{symbol}", response_model=AssetResponse, summary="Get asset detail by symbol")
async def get_asset(
    symbol: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve asset detail and active markets for a single symbol."""
    query = (
        select(Asset)
        .options(selectinload(Asset.markets))
        .where(Asset.symbol == symbol.upper())
    )
    res = await db.execute(query)
    asset = res.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset symbol '{symbol.upper()}' not found in registry.",
        )

    return AssetResponse(
        id=asset.id,
        name=asset.name,
        symbol=asset.symbol,
        asset_class=asset.asset_class,
        primary_sector=asset.primary_sector,
        is_active=asset.is_active,
        markets=[
            MarketResponse(
                id=m.id,
                exchange_id=m.exchange_id,
                symbol=m.symbol,
                quote_asset=m.quote_asset,
                is_active=m.is_active,
            )
            for m in asset.markets
        ],
    )


@router.get("/ohlcv/{symbol}", response_model=list[CandleResponse], summary="Query historical OHLCV candlesticks")
async def get_ohlcv(
    symbol: str,
    timeframe: Timeframe = Query(Timeframe.H1, description="Candlestick timeframe"),
    exchange: str = Query("binance", description="Exchange identifier"),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Fetch stored historical candlesticks for asset pair."""
    # Find market
    market_id = f"{exchange.lower()}:{symbol.upper()}/USDT"
    query = (
        select(OHLCV)
        .where(OHLCV.market_id == market_id, OHLCV.timeframe == timeframe.value)
        .order_by(desc(OHLCV.time))
        .limit(limit)
    )
    res = await db.execute(query)
    candles = res.scalars().all()

    # Return chronological order (oldest to newest)
    candles_reversed = list(reversed(candles))
    return [
        CandleResponse(
            time=c.time.isoformat(),
            open=c.open,
            high=c.high,
            low=c.low,
            close=c.close,
            volume=c.volume,
            validation_status=c.validation_status,
        )
        for c in candles_reversed
    ]
