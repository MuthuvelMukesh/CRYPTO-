"""Ingestion pipeline coordinator for asset seeding, OHLCV ingestion, and DB storage."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import AssetClass, Timeframe
from src.database.models import OHLCV, Asset, Exchange, Market
from src.ingestion.providers.base import BaseDataProvider
from src.utils.logging import get_logger
from src.utils.time import to_utc_datetime
from src.validation.ohlcv_validator import OHLCVValidator

logger = get_logger("ingestion.pipeline")

# Canonical bootstrap asset registry
DEFAULT_UNIVERSE = [
    {
        "id": "BTC",
        "name": "Bitcoin",
        "symbol": "BTC",
        "asset_class": AssetClass.CORE,
        "primary_sector": "Store of Value",
        "market": "BTC/USDT",
    },
    {
        "id": "ETH",
        "name": "Ethereum",
        "symbol": "ETH",
        "asset_class": AssetClass.CORE,
        "primary_sector": "Layer 1",
        "market": "ETH/USDT",
    },
    {
        "id": "SOL",
        "name": "Solana",
        "symbol": "SOL",
        "asset_class": AssetClass.ALTCOIN,
        "primary_sector": "Layer 1",
        "market": "SOL/USDT",
    },
    {
        "id": "BNB",
        "name": "BNB",
        "symbol": "BNB",
        "asset_class": AssetClass.ALTCOIN,
        "primary_sector": "Exchange",
        "market": "BNB/USDT",
    },
    {
        "id": "NEAR",
        "name": "NEAR Protocol",
        "symbol": "NEAR",
        "asset_class": AssetClass.ALTCOIN,
        "primary_sector": "AI",
        "market": "NEAR/USDT",
    },
    {
        "id": "RENDER",
        "name": "Render",
        "symbol": "RENDER",
        "asset_class": AssetClass.ALTCOIN,
        "primary_sector": "DePIN",
        "market": "RENDER/USDT",
    },
    {
        "id": "DOGE",
        "name": "Dogecoin",
        "symbol": "DOGE",
        "asset_class": AssetClass.MEME,
        "primary_sector": "Meme",
        "market": "DOGE/USDT",
    },
    {
        "id": "PEPE",
        "name": "Pepe",
        "symbol": "PEPE",
        "asset_class": AssetClass.MEME,
        "primary_sector": "Meme",
        "market": "PEPE/USDT",
    },
]


async def seed_default_universe(session: AsyncSession, exchange_id: str = "binance") -> None:
    """Seed base assets, exchanges, and tradable markets into database if not present."""
    # Ensure exchange exists
    res = await session.execute(select(Exchange).where(Exchange.id == exchange_id))
    exchange = res.scalar_one_or_none()
    if not exchange:
        exchange = Exchange(id=exchange_id, name=exchange_id.capitalize(), is_active=True)
        session.add(exchange)
        await session.flush()

    for item in DEFAULT_UNIVERSE:
        # Check asset
        asset_res = await session.execute(select(Asset).where(Asset.id == item["id"]))
        asset = asset_res.scalar_one_or_none()
        if not asset:
            asset = Asset(
                id=item["id"],
                name=item["name"],
                symbol=item["symbol"],
                asset_class=item["asset_class"].value,
                primary_sector=item["primary_sector"],
                is_active=True,
            )
            session.add(asset)
            await session.flush()

        # Check market
        market_id = f"{exchange_id}:{item['market']}"
        m_res = await session.execute(select(Market).where(Market.id == market_id))
        market = m_res.scalar_one_or_none()
        if not market:
            quote = item["market"].split("/")[1]
            market = Market(
                id=market_id,
                exchange_id=exchange_id,
                asset_id=item["id"],
                quote_asset=quote,
                symbol=item["market"],
                is_active=True,
            )
            session.add(market)

    await session.commit()
    logger.info("default_universe_seeded", count=len(DEFAULT_UNIVERSE))


async def ingest_market_ohlcv(
    session: AsyncSession,
    provider: BaseDataProvider,
    symbol: str,
    market_id: str,
    timeframe: Timeframe = Timeframe.H1,
    limit: int = 100,
) -> int:
    """
    Fetch OHLCV candles, validate, normalize timestamps, and store in database.
    Returns count of successfully saved valid candles.
    """
    raw_candles = await provider.fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
    if not raw_candles:
        logger.warning("no_candles_received", symbol=symbol, provider=provider.name)
        return 0

    # Validate and clean sequence
    cleaned_candles, warnings = OHLCVValidator.validate_and_clean_series(
        raw_candles, timeframe=timeframe
    )
    if warnings:
        logger.info("validation_sequence_warnings", symbol=symbol, warnings=warnings)

    saved_count = 0
    for c in cleaned_candles:
        candle_dt = to_utc_datetime(c.timestamp_ms)

        # Upsert logic: query existing candle or create new
        existing_res = await session.execute(
            select(OHLCV).where(
                OHLCV.market_id == market_id,
                OHLCV.timeframe == timeframe.value,
                OHLCV.time == candle_dt,
            )
        )
        existing = existing_res.scalar_one_or_none()
        if existing:
            existing.open = c.open
            existing.high = c.high
            existing.low = c.low
            existing.close = c.close
            existing.volume = c.volume
            existing.validation_status = c.validation_status.value
        else:
            record = OHLCV(
                time=candle_dt,
                market_id=market_id,
                timeframe=timeframe.value,
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
                validation_status=c.validation_status.value,
            )
            session.add(record)
        saved_count += 1

    await session.commit()
    logger.info(
        "candles_ingested_and_stored",
        symbol=symbol,
        count=saved_count,
        timeframe=timeframe.value,
    )
    return saved_count
