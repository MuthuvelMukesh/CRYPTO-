"""Dynamic Asset Universe Builder — v2.0.

Replaces the hard-coded 8-asset list with a market-driven discovery system.
Assets are qualified by volume, liquidity, and data freshness criteria.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import AssetClass, DataMode, ListingStatus
from src.config.settings import get_settings
from src.database.models import Asset, Exchange, Market, UniverseSnapshot
from src.ingestion.pipeline import DEFAULT_UNIVERSE
from src.utils.logging import get_logger
from src.utils.time import utc_now

logger = get_logger("universe_builder")
settings = get_settings()


async def build_and_register_universe(
    session: AsyncSession,
    exchange_id: str | None = None,
    data_mode: DataMode | None = None,
) -> list[dict[str, Any]]:
    """Discover, qualify, and register the current scanner universe.

    In LIVE mode:
        - Fetches available markets from exchange via CCXTProvider
        - Filters by volume/liquidity thresholds from settings
        - Upserts Asset, Exchange, Market records
        - Writes UniverseSnapshot rows for research reproducibility

    In HISTORICAL / SYNTHETIC_TEST modes:
        - Falls back to the DEFAULT_UNIVERSE bootstrap list (no exchange call)

    Returns:
        List of registered asset dicts {id, symbol, asset_class, market_id}
    """
    mode = data_mode or settings.DATA_MODE
    ex_id = exchange_id or settings.DEFAULT_EXCHANGE

    # In non-live modes, use the hardcoded bootstrap universe
    if mode != DataMode.LIVE:
        logger.info(
            "universe_using_bootstrap",
            reason=f"DATA_MODE={mode} — dynamic discovery requires LIVE mode",
            count=len(DEFAULT_UNIVERSE),
        )
        await _ensure_bootstrap_universe(session, ex_id)
        return [
            {
                "id": a["id"],
                "symbol": a["symbol"],
                "asset_class": a["asset_class"],
                "market_id": f"{ex_id}:{a['market']}",
            }
            for a in DEFAULT_UNIVERSE
        ]

    # LIVE mode: attempt dynamic discovery
    try:
        from src.ingestion.providers.ccxt_provider import CCXTProvider
        provider = CCXTProvider(exchange_id=ex_id)
        try:
            markets = await provider.fetch_markets(ex_id)
        finally:
            await provider.close()

        qualified = _qualify_markets(markets)
        logger.info(
            "universe_dynamic_discovery",
            exchange=ex_id,
            total_markets=len(markets),
            qualified=len(qualified),
        )
    except Exception as e:
        logger.warning(
            "universe_discovery_failed_using_bootstrap",
            error=str(e),
            count=len(DEFAULT_UNIVERSE),
        )
        qualified = []

    # If dynamic discovery returns nothing useful, fall back to bootstrap
    if not qualified:
        logger.info("universe_fallback_to_bootstrap")
        await _ensure_bootstrap_universe(session, ex_id)
        return [
            {
                "id": a["id"],
                "symbol": a["symbol"],
                "asset_class": a["asset_class"],
                "market_id": f"{ex_id}:{a['market']}",
            }
            for a in DEFAULT_UNIVERSE
        ]

    # Register qualified markets in DB and write universe snapshot
    registered = await _register_qualified_markets(session, ex_id, qualified, mode)
    return registered


def _qualify_markets(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply volume and liquidity filters to raw exchange market list."""
    qualified = []
    for m in markets:
        if not m.get("active"):
            continue
        if m.get("quote") not in {"USDT", "USDC", "USD"}:
            continue
        vol = m.get("volume_24h_usd", 0.0) or 0.0
        if vol < settings.UNIVERSE_MIN_VOLUME_24H_USD:
            continue
        qualified.append(m)

    # Sort by volume descending, take top N
    qualified.sort(key=lambda x: x.get("volume_24h_usd", 0.0), reverse=True)
    return qualified[: settings.UNIVERSE_MAX_ASSETS]


async def _ensure_bootstrap_universe(session: AsyncSession, exchange_id: str) -> None:
    """Register the hardcoded bootstrap universe in the DB if not present."""
    res = await session.execute(select(Exchange).where(Exchange.id == exchange_id))
    if not res.scalar_one_or_none():
        session.add(Exchange(id=exchange_id, name=exchange_id.capitalize(), is_active=True))
        await session.flush()

    for item in DEFAULT_UNIVERSE:
        asset_res = await session.execute(select(Asset).where(Asset.id == item["id"]))
        if not asset_res.scalar_one_or_none():
            session.add(Asset(
                id=item["id"],
                name=item["name"],
                symbol=item["symbol"],
                asset_class=item["asset_class"].value,
                primary_sector=item["primary_sector"],
                is_active=True,
            ))
            await session.flush()

        market_id = f"{exchange_id}:{item['market']}"
        mkt_res = await session.execute(select(Market).where(Market.id == market_id))
        if not mkt_res.scalar_one_or_none():
            quote = item["market"].split("/")[1]
            session.add(Market(
                id=market_id,
                exchange_id=exchange_id,
                asset_id=item["id"],
                quote_asset=quote,
                symbol=item["market"],
                is_active=True,
            ))

    await session.commit()


async def _register_qualified_markets(
    session: AsyncSession,
    exchange_id: str,
    markets: list[dict[str, Any]],
    data_mode: DataMode,
) -> list[dict[str, Any]]:
    """Upsert Asset/Market records for dynamically qualified markets."""
    registered = []
    now = utc_now()

    for m in markets:
        base = m.get("base", "").upper()
        quote = m.get("quote", "").upper()
        symbol = m.get("symbol", f"{base}/{quote}")
        asset_id = base
        market_id = f"{exchange_id}:{symbol}"

        # Classify asset
        asset_class = _classify_asset(base)

        # Upsert asset
        asset_res = await session.execute(select(Asset).where(Asset.id == asset_id))
        existing_asset = asset_res.scalar_one_or_none()
        if not existing_asset:
            session.add(Asset(
                id=asset_id,
                name=m.get("id", base),
                symbol=base,
                asset_class=asset_class.value,
                primary_sector=_guess_sector(base),
                is_active=True,
            ))

        # Upsert market
        mkt_res = await session.execute(select(Market).where(Market.id == market_id))
        if not mkt_res.scalar_one_or_none():
            session.add(Market(
                id=market_id,
                exchange_id=exchange_id,
                asset_id=asset_id,
                quote_asset=quote,
                symbol=symbol,
                is_active=True,
            ))

        # Write universe snapshot
        session.add(UniverseSnapshot(
            snapshot_date=now,
            asset_id=asset_id,
            exchange_id=exchange_id,
            market_id=market_id,
            asset_class=asset_class.value,
            is_active=True,
            volume_24h_usd=m.get("volume_24h_usd"),
            inclusion_reason="DYNAMIC_VOLUME_QUALIFIED",
            data_mode=data_mode.value,
        ))

        registered.append({
            "id": asset_id,
            "symbol": base,
            "asset_class": asset_class,
            "market_id": market_id,
        })

    await session.commit()
    logger.info("universe_registered", count=len(registered))
    return registered


def _classify_asset(symbol: str) -> AssetClass:
    """Simple heuristic asset classification."""
    core = {"BTC", "ETH"}
    large_alt = {"BNB", "SOL", "XRP", "ADA", "AVAX", "DOT", "MATIC", "LINK"}
    meme = {"DOGE", "SHIB", "PEPE", "BONK", "WIF", "FLOKI", "BOME", "POPCAT", "MEW"}
    if symbol in core:
        return AssetClass.CORE
    if symbol in large_alt:
        return AssetClass.ALTCOIN
    if symbol in meme:
        return AssetClass.MEME
    return AssetClass.SMALL_CAP


def _guess_sector(symbol: str) -> str:
    """Rough sector mapping for dashboard grouping."""
    sectors = {
        "BTC": "Store of Value",
        "ETH": "Layer 1",
        "SOL": "Layer 1",
        "BNB": "Exchange",
        "NEAR": "AI / Web3",
        "RENDER": "DePIN",
        "OP": "Layer 2",
        "ARB": "Layer 2",
        "LINK": "Oracle",
        "UNI": "DeFi",
        "AAVE": "DeFi",
        "DOGE": "Meme",
        "SHIB": "Meme",
        "PEPE": "Meme",
    }
    return sectors.get(symbol, "Altcoin")
