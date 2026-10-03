"""Asset catalog and historical market data query endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.deps import get_db
from src.config.constants import AssetClass, Timeframe
from src.database.models import OHLCV, Asset, Feature

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


class AssetFeaturesResponse(BaseModel):
    asset_id: str
    symbol: str
    time: str
    timeframe: str

    # Momentum
    return_1d: float | None = None
    return_3d: float | None = None
    return_7d: float | None = None
    return_14d: float | None = None
    return_30d: float | None = None
    return_90d: float | None = None
    momentum_acceleration: float | None = None
    volatility_adjusted_momentum: float | None = None

    # Relative Strength
    rs_btc_30d: float | None = None
    rs_eth_30d: float | None = None
    rs_sector_30d: float | None = None

    # Trend
    ema20_ratio: float | None = None
    ema50_ratio: float | None = None
    ema200_ratio: float | None = None
    adx_14: float | None = None
    atr_14_pct: float | None = None

    # Volume & Liquidity
    volume_to_20d_avg: float | None = None
    volume_acceleration: float | None = None
    turnover_ratio: float | None = None
    spread_est_bps: float | None = None

    # Volatility & Risk
    realized_vol_30d: float | None = None
    downside_vol_30d: float | None = None
    max_drawdown_90d: float | None = None


@router.get(
    "/assets/{symbol}/features",
    response_model=AssetFeaturesResponse,
    summary="Get latest quantitative feature set for asset",
)
async def get_asset_features(
    symbol: str,
    timeframe: Timeframe = Query(Timeframe.H1, description="Feature timeframe"),
    db: AsyncSession = Depends(get_db),
) -> AssetFeaturesResponse:
    """Retrieve latest calculated feature vector for a specific asset."""
    # Find asset
    asset_query = select(Asset).where(Asset.symbol == symbol.upper())
    asset_res = await db.execute(asset_query)
    asset = asset_res.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset symbol '{symbol.upper()}' not found in registry.",
        )

    # Query latest feature
    feat_query = (
        select(Feature)
        .where(Feature.asset_id == asset.id, Feature.timeframe == timeframe.value)
        .order_by(desc(Feature.time))
        .limit(1)
    )
    feat_res = await db.execute(feat_query)
    feat = feat_res.scalar_one_or_none()

    if not feat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Features for asset '{symbol.upper()}' ({timeframe.value}) not found.",
        )

    return AssetFeaturesResponse(
        asset_id=feat.asset_id,
        symbol=asset.symbol,
        time=feat.time.isoformat(),
        timeframe=feat.timeframe,
        return_1d=feat.return_1d,
        return_3d=feat.return_3d,
        return_7d=feat.return_7d,
        return_14d=feat.return_14d,
        return_30d=feat.return_30d,
        return_90d=feat.return_90d,
        momentum_acceleration=feat.momentum_acceleration,
        volatility_adjusted_momentum=feat.volatility_adjusted_momentum,
        rs_btc_30d=feat.rs_btc_30d,
        rs_eth_30d=feat.rs_eth_30d,
        rs_sector_30d=feat.rs_sector_30d,
        ema20_ratio=feat.ema20_ratio,
        ema50_ratio=feat.ema50_ratio,
        ema200_ratio=feat.ema200_ratio,
        adx_14=feat.adx_14,
        atr_14_pct=feat.atr_14_pct,
        volume_to_20d_avg=feat.volume_to_20d_avg,
        volume_acceleration=feat.volume_acceleration,
        turnover_ratio=feat.turnover_ratio,
        spread_est_bps=feat.spread_est_bps,
        realized_vol_30d=feat.realized_vol_30d,
        downside_vol_30d=feat.downside_vol_30d,
        max_drawdown_90d=feat.max_drawdown_90d,
    )


class WatchlistResponse(BaseModel):
    id: str
    user_id: str
    symbol: str
    tags: str
    notes: str
    created_at: str


class AddWatchlistRequest(BaseModel):
    symbol: str
    tags: str = ""
    notes: str = ""


@router.get("/watchlist", response_model=list[WatchlistResponse], summary="Get user watchlist of monitored assets")
@router.get("/assets/watchlist", response_model=list[WatchlistResponse], summary="Get user watchlist of monitored assets")
async def get_watchlist(
    db: AsyncSession = Depends(get_db),
):
    """Retrieve user-tracked watchlist assets with custom tags and notes."""
    import uuid
    from src.database.models.watchlist import WatchlistItem

    res = await db.execute(select(WatchlistItem).order_by(desc(WatchlistItem.created_at)))
    items = res.scalars().all()
    return [
        WatchlistResponse(
            id=i.id,
            user_id=i.user_id,
            symbol=i.symbol,
            tags=i.tags or "",
            notes=i.notes or "",
            created_at=i.created_at.isoformat() if i.created_at else "",
        )
        for i in items
    ]


@router.post("/watchlist", response_model=WatchlistResponse, summary="Add asset to user watchlist with tags and notes")
@router.post("/assets/watchlist", response_model=WatchlistResponse, summary="Add asset to user watchlist with tags and notes")
async def add_to_watchlist(
    req: AddWatchlistRequest,
    db: AsyncSession = Depends(get_db),
):
    """Add or update an asset in the user watchlist."""
    import uuid
    from src.database.models.watchlist import WatchlistItem

    symbol = req.symbol.upper().strip()
    res = await db.execute(select(WatchlistItem).where(WatchlistItem.symbol == symbol))
    existing = res.scalar_one_or_none()
    if existing:
        existing.tags = req.tags
        existing.notes = req.notes
        await db.commit()
        return WatchlistResponse(
            id=existing.id,
            user_id=existing.user_id,
            symbol=existing.symbol,
            tags=existing.tags or "",
            notes=existing.notes or "",
            created_at=existing.created_at.isoformat() if existing.created_at else "",
        )

    item = WatchlistItem(
        id=str(uuid.uuid4()),
        user_id="default_user",
        symbol=symbol,
        tags=req.tags,
        notes=req.notes,
    )
    db.add(item)
    await db.commit()
    return WatchlistResponse(
        id=item.id,
        user_id=item.user_id,
        symbol=item.symbol,
        tags=item.tags or "",
        notes=item.notes or "",
        created_at=item.created_at.isoformat() if item.created_at else "",
    )


@router.delete("/watchlist/{symbol}", summary="Remove asset from user watchlist")
@router.delete("/assets/watchlist/{symbol}", summary="Remove asset from user watchlist")
async def remove_from_watchlist(
    symbol: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove an asset from user watchlist."""
    from src.database.models.watchlist import WatchlistItem

    sym = symbol.upper().strip()
    res = await db.execute(select(WatchlistItem).where(WatchlistItem.symbol == sym))
    item = res.scalar_one_or_none()
    if item:
        await db.delete(item)
        await db.commit()
    return {"symbol": sym, "removed": True}

