"""Feature calculation coordinator and database persistence pipeline."""

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import Timeframe
from src.database.models import OHLCV, Feature
from src.features.liquidity import calculate_liquidity_features
from src.features.momentum import calculate_momentum_features
from src.features.relative_strength import calculate_relative_strength
from src.features.trend import calculate_trend_features
from src.features.volatility import calculate_volatility_features
from src.features.volume import calculate_volume_features
from src.utils.logging import get_logger

logger = get_logger("features.pipeline")


async def calculate_and_store_asset_features(
    session: AsyncSession,
    asset_id: str,
    timeframe: Timeframe = Timeframe.H1,
    exchange_id: str = "binance",
) -> Feature | None:
    """Calculate and persist all quantitative features for an asset at latest candle."""
    market_id = f"{exchange_id}:{asset_id}/USDT"

    # Fetch historical candles for asset
    query = (
        select(OHLCV)
        .where(OHLCV.market_id == market_id, OHLCV.timeframe == timeframe.value)
        .order_by(desc(OHLCV.time))
        .limit(300)
    )
    res = await session.execute(query)
    candles = list(reversed(res.scalars().all()))

    if len(candles) < 20:
        logger.warning("insufficient_candles_for_features", asset=asset_id, count=len(candles))
        return None

    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    volumes = [c.volume for c in candles]
    latest_time = candles[-1].time

    # Fetch BTC benchmark closes for relative strength if not BTC itself
    btc_closes = None
    if asset_id != "BTC":
        btc_res = await session.execute(
            select(OHLCV.close)
            .where(OHLCV.market_id == f"{exchange_id}:BTC/USDT", OHLCV.timeframe == timeframe.value)
            .order_by(desc(OHLCV.time))
            .limit(len(closes))
        )
        btc_candles = list(reversed(btc_res.scalars().all()))
        if len(btc_candles) == len(closes):
            btc_closes = btc_candles

    # Fetch ETH benchmark closes if not ETH itself
    eth_closes = None
    if asset_id not in ("ETH", "BTC"):
        eth_res = await session.execute(
            select(OHLCV.close)
            .where(OHLCV.market_id == f"{exchange_id}:ETH/USDT", OHLCV.timeframe == timeframe.value)
            .order_by(desc(OHLCV.time))
            .limit(len(closes))
        )
        eth_candles = list(reversed(eth_res.scalars().all()))
        if len(eth_candles) == len(closes):
            eth_closes = eth_candles

    # 1. Momentum
    mom = calculate_momentum_features(closes)

    # 2. Relative Strength
    rs = calculate_relative_strength(closes, btc_prices=btc_closes, eth_prices=eth_closes)

    # 3. Trend
    trend = calculate_trend_features(highs, lows, closes)

    # 4. Volume
    vol = calculate_volume_features(volumes, closes)

    # 5. Volatility
    volatility = calculate_volatility_features(highs, lows, closes)

    # 6. Liquidity
    liq = calculate_liquidity_features(highs, lows, volume_24h_usd=vol.dollar_volume_24h)

    # Upsert Feature into DB
    feat_res = await session.execute(
        select(Feature).where(
            Feature.time == latest_time,
            Feature.asset_id == asset_id,
            Feature.timeframe == timeframe.value,
        )
    )
    feature = feat_res.scalar_one_or_none()
    if not feature:
        feature = Feature(
            time=latest_time,
            asset_id=asset_id,
            timeframe=timeframe.value,
        )
        session.add(feature)

    # Assign calculated attributes
    feature.return_1d = mom.return_1d
    feature.return_3d = mom.return_3d
    feature.return_7d = mom.return_7d
    feature.return_14d = mom.return_14d
    feature.return_30d = mom.return_30d
    feature.return_90d = mom.return_90d
    feature.momentum_acceleration = mom.momentum_acceleration
    feature.volatility_adjusted_momentum = mom.volatility_adjusted_momentum

    feature.rs_btc_30d = rs.rs_btc_30d
    feature.rs_eth_30d = rs.rs_eth_30d
    feature.rs_sector_30d = rs.rs_sector_30d

    feature.ema20_ratio = trend.ema20_ratio
    feature.ema50_ratio = trend.ema50_ratio
    feature.ema200_ratio = trend.ema200_ratio
    feature.adx_14 = trend.adx_14
    feature.atr_14_pct = trend.atr_14_pct

    feature.volume_to_20d_avg = vol.volume_to_20_avg
    feature.volume_acceleration = vol.volume_acceleration
    feature.turnover_ratio = vol.turnover_ratio

    feature.realized_vol_30d = volatility.realized_vol_30d
    feature.downside_vol_30d = volatility.downside_vol_30d
    feature.max_drawdown_90d = volatility.max_drawdown_90d
    feature.spread_est_bps = liq.spread_est_bps

    await session.commit()
    logger.info("asset_features_computed_and_stored", asset=asset_id, time=latest_time.isoformat())
    return feature
