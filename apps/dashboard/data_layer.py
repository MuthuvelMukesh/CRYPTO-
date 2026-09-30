"""Data extraction and state aggregation layer for Streamlit Quantitative Lab."""

import asyncio
import concurrent.futures
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import desc, select

from src.config.constants import Timeframe
from src.database.models import OHLCV, Asset, Feature, Score
from src.database.session import get_session_factory, init_db
from src.features.market_regime import classify_market_regime
from src.features.pipeline import calculate_and_store_asset_features
from src.ingestion.pipeline import seed_default_universe
from src.scoring.engine import score_universe


def run_async(coro):
    """Run an async coroutine safely on a dedicated thread with its own event loop."""
    def _runner():
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(_runner).result()


class DashboardDataLayer:
    """Provides high-performance data querying for all dashboard views."""

    @classmethod
    def ensure_seeded_data(cls) -> None:
        """Ensure initial universe and baseline candles exist in DB."""
        async def _seed():
            await init_db()
            factory = get_session_factory()
            async with factory() as session:
                await seed_default_universe(session)
                # Check if OHLCV data exists
                res = await session.execute(select(OHLCV).limit(1))
                if not res.scalar_one_or_none():
                    # Generate synthetic baseline candles for demonstration
                    base_ms = int(datetime.now(UTC).timestamp() * 1000) - (200 * 3600 * 1000)
                    assets_map = {
                        "BTC": (64000.0, 1.02),
                        "ETH": (3400.0, 1.015),
                        "SOL": (155.0, 1.03),
                        "BNB": (590.0, 1.008),
                        "NEAR": (5.20, 1.04),
                        "RENDER": (6.40, 1.035),
                        "DOGE": (0.125, 1.06),
                        "PEPE": (0.0000095, 1.08),
                    }
                    for sym, (base_p, trend_factor) in assets_map.items():
                        market_id = f"binance:{sym}/USDT"
                        curr_p = base_p
                        for i in range(120):
                            t = datetime.fromtimestamp((base_ms + (i * 3600 * 1000)) / 1000.0, tz=UTC)
                            change = (0.002 * (i % 5 - 2)) + ((trend_factor - 1.0) * 0.1)
                            curr_p = max(0.000001, curr_p * (1.0 + change))
                            candle = OHLCV(
                                time=t,
                                market_id=market_id,
                                timeframe="1h",
                                open=curr_p * 0.998,
                                high=curr_p * 1.012,
                                low=curr_p * 0.992,
                                close=curr_p,
                                volume=1000.0 + (i * 15.0),
                                validation_status="GOOD",
                            )
                            session.add(candle)
                    await session.commit()

                    # Compute features & scores
                    for sym in assets_map:
                        await calculate_and_store_asset_features(session, sym, Timeframe.H1)
                    await score_universe(session, Timeframe.H1)

        run_async(_seed())

    @classmethod
    def get_scanner_data(cls) -> pd.DataFrame:
        """Retrieve full scanner dataset with scores, price changes, and risk flags."""
        async def _query():
            cls.ensure_seeded_data()
            factory = get_session_factory()
            async with factory() as session:
                query = (
                    select(Score, Asset)
                    .join(Asset, Score.asset_id == Asset.id)
                    .order_by(desc(Score.opportunity_score))
                )
                res = await session.execute(query)
                rows = res.all()

                data: list[dict] = []
                for score_obj, asset_obj in rows:
                    # Get latest price and features
                    feat_res = await session.execute(
                        select(Feature)
                        .where(Feature.asset_id == asset_obj.id, Feature.timeframe == "1h")
                        .order_by(desc(Feature.time))
                        .limit(1)
                    )
                    feat = feat_res.scalar_one_or_none()

                    ohlcv_res = await session.execute(
                        select(OHLCV.close)
                        .where(OHLCV.market_id == f"binance:{asset_obj.id}/USDT")
                        .order_by(desc(OHLCV.time))
                        .limit(1)
                    )
                    last_price = ohlcv_res.scalar_one_or_none() or 0.0

                    r1 = getattr(feat, "return_1d", 0.0) or 0.0
                    r7 = getattr(feat, "return_7d", 0.0) or 0.0
                    r30 = getattr(feat, "return_30d", 0.0) or 0.0

                    data.append({
                        "Symbol": asset_obj.symbol,
                        "Name": asset_obj.name,
                        "Class": asset_obj.asset_class,
                        "Sector": asset_obj.primary_sector,
                        "Price": last_price,
                        "1D %": round(r1 * 100.0, 2),
                        "7D %": round(r7 * 100.0, 2),
                        "30D %": round(r30 * 100.0, 2),
                        "Opportunity": score_obj.opportunity_score,
                        "Momentum": score_obj.momentum_score,
                        "Relative Strength": score_obj.relative_strength_score,
                        "Trend": score_obj.trend_score,
                        "Volume": getattr(score_obj, "volume_score", 50.0) or 50.0,
                        "Quality": score_obj.quality_score,
                        "Risk": score_obj.risk_score,
                        "Liquidity": score_obj.liquidity_score,
                        "Risk Flags": score_obj.risk_flags or [],
                        "Model": score_obj.model_type,
                        "Breakdown": score_obj.breakdown_json,
                    })

                return pd.DataFrame(data)

        return run_async(_query())

    @classmethod
    def get_market_regime(cls):
        """Retrieve latest macro regime classification."""
        async def _query():
            cls.ensure_seeded_data()
            factory = get_session_factory()
            async with factory() as session:
                # Query BTC and ETH candles
                btc_res = await session.execute(
                    select(OHLCV.close)
                    .where(OHLCV.market_id == "binance:BTC/USDT")
                    .order_by(desc(OHLCV.time))
                    .limit(100)
                )
                btc_closes = list(reversed(btc_res.scalars().all()))

                eth_res = await session.execute(
                    select(OHLCV.close)
                    .where(OHLCV.market_id == "binance:ETH/USDT")
                    .order_by(desc(OHLCV.time))
                    .limit(100)
                )
                eth_closes = list(reversed(eth_res.scalars().all()))

                if not btc_closes:
                    return {
                        "regime": "NEUTRAL",
                        "confidence": 0.60,
                        "btc_above_ema50": True,
                        "breadth_pct": 62.5,
                        "rationale": ["Bootstrap Model"],
                    }

                reg = classify_market_regime(
                    btc_closes=btc_closes,
                    eth_closes=eth_closes if len(eth_closes) == len(btc_closes) else None,
                )
                return {
                    "regime": reg.regime.value,
                    "confidence": reg.confidence,
                    "btc_above_ema50": reg.btc_above_ema50,
                    "breadth_pct": reg.market_breadth_pct,
                    "rationale": reg.rationale,
                }

        return run_async(_query())

    @classmethod
    def get_candlestick_data(cls, symbol: str) -> pd.DataFrame:
        """Fetch historical candlesticks for detailed charting."""
        async def _query():
            cls.ensure_seeded_data()
            factory = get_session_factory()
            async with factory() as session:
                market_id = f"binance:{symbol.upper()}/USDT"
                res = await session.execute(
                    select(OHLCV)
                    .where(OHLCV.market_id == market_id)
                    .order_by(desc(OHLCV.time))
                    .limit(120)
                )
                candles = list(reversed(res.scalars().all()))
                if not candles:
                    return pd.DataFrame()

                data = [
                    {
                        "time": c.time,
                        "open": c.open,
                        "high": c.high,
                        "low": c.low,
                        "close": c.close,
                        "volume": c.volume,
                    }
                    for c in candles
                ]
                return pd.DataFrame(data)

        return run_async(_query())
