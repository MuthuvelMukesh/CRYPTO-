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

    @classmethod
    def run_backtest(
        cls,
        strategy_name: str = "MomentumBreakout",
        initial_capital: float = 100000.0,
        days: int = 90,
        slippage_model: str = "market_impact",
    ) -> dict:
        """Execute a backtest simulation and return metrics, equity series, and trade logs."""
        from datetime import timedelta

        import numpy as np

        from src.backtesting.engine import BacktestEngine
        from src.backtesting.models import BacktestConfig, SlippageModelType
        from src.backtesting.strategies import get_strategy

        cls.ensure_seeded_data()
        now = datetime.now(UTC)
        start_date = now - timedelta(days=days)

        slip_type = (
            SlippageModelType.MARKET_IMPACT
            if slippage_model == "market_impact"
            else (SlippageModelType.FIXED_BPS if slippage_model == "fixed_bps" else SlippageModelType.NONE)
        )

        config = BacktestConfig(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=now,
            initial_capital=initial_capital,
            slippage_model=slip_type,
        )
        strategy = get_strategy(strategy_name)

        # Generate realistic multi-asset candle and feature series
        symbols = ["BTC", "ETH", "SOL", "BNB", "NEAR", "RENDER", "DOGE"]
        base_prices = {"BTC": 64000.0, "ETH": 3400.0, "SOL": 155.0, "BNB": 590.0, "NEAR": 5.20, "RENDER": 6.40, "DOGE": 0.125}
        candles: dict[str, list[dict]] = {}
        features: dict[str, list[dict]] = {}

        for sym in symbols:
            np.random.seed(abs(hash(sym + strategy_name)) % 1000000)
            p0 = base_prices.get(sym, 10.0)
            c_list = []
            f_list = []
            curr_p = p0

            for d in range(days + 1):
                t = start_date + timedelta(days=d)
                ret = float(np.random.normal(0.002, 0.025))
                open_p = curr_p
                close_p = max(0.0001, curr_p * (1.0 + ret))
                high_p = max(open_p, close_p) * (1.0 + abs(float(np.random.normal(0.0, 0.012))))
                low_p = min(open_p, close_p) * (1.0 - abs(float(np.random.normal(0.0, 0.012))))
                vol_usd = float(np.random.uniform(200000.0, 3000000.0))
                curr_p = close_p

                c_list.append({
                    "time": t,
                    "open": round(open_p, 4),
                    "high": round(high_p, 4),
                    "low": round(low_p, 4),
                    "close": round(close_p, 4),
                    "volume": round(vol_usd / close_p, 2),
                    "volume_usd": round(vol_usd, 2),
                })
                f_list.append({
                    "time": t,
                    "return_30d": float(np.random.uniform(-0.08, 0.25)),
                    "rs_btc_30d": float(np.random.uniform(-0.10, 0.20)),
                    "ema20_ratio": float(np.random.uniform(0.96, 1.07)),
                    "ema50_ratio": float(np.random.uniform(0.94, 1.09)),
                    "adx_14": float(np.random.uniform(16.0, 35.0)),
                    "volume_to_20d_avg": float(np.random.uniform(0.9, 2.2)),
                    "volatility_adjusted_momentum": float(np.random.uniform(-0.5, 2.2)),
                    "opportunity_score": float(np.random.uniform(45.0, 94.0)),
                    "risk_flags": [],
                })

            candles[sym] = c_list
            features[sym] = f_list

        engine = BacktestEngine(config, strategy)
        result = engine.run(historical_candles=candles, historical_features=features)

        equity_df = pd.DataFrame(result.equity_curve)
        if not equity_df.empty:
            equity_df["time"] = pd.to_datetime(equity_df["time"])

        trades_df = pd.DataFrame(result.trades)
        if not trades_df.empty:
            trades_df["entry_time"] = pd.to_datetime(trades_df["entry_time"]).dt.strftime("%Y-%m-%d %H:%M")
            trades_df["exit_time"] = pd.to_datetime(trades_df["exit_time"]).dt.strftime("%Y-%m-%d %H:%M")

        return {
            "result_id": result.id,
            "metrics": result.metrics,
            "equity_df": equity_df,
            "trades_df": trades_df,
            "total_trades": result.total_trades,
        }

    @classmethod
    def get_paper_portfolio(cls, account_id: str = "default_paper") -> dict:
        """Fetch real-time paper account summary and positions."""
        from src.paper.broker import PaperBroker

        async def _query():
            cls.ensure_seeded_data()
            factory = get_session_factory()
            async with factory() as session:
                broker = PaperBroker()
                summary = await broker.get_portfolio_summary(session, account_id=account_id)
                positions_data = [
                    {
                        "Asset": p.symbol,
                        "Side": p.side,
                        "Quantity": p.quantity,
                        "Entry Price": f"${p.avg_entry_price:,.2f}",
                        "Current Price": f"${p.current_price:,.2f}",
                        "Market Value": f"${p.market_value:,.2f}",
                        "Unrealized P&L": f"{p.unrealized_pnl:+,.2f} ({p.unrealized_pnl_pct:+.2f}%)",
                        "Realized P&L": f"${p.realized_pnl:+,.2f}",
                    }
                    for p in summary.open_positions
                ]
                return {
                    "account_id": summary.account_id,
                    "cash_balance": summary.cash_balance,
                    "invested_capital": summary.invested_capital,
                    "total_equity": summary.total_equity,
                    "total_return_pct": summary.total_return_pct,
                    "unrealized_pnl": summary.unrealized_pnl,
                    "realized_pnl": summary.realized_pnl,
                    "drawdown_pct": summary.drawdown_pct,
                    "meme_exposure_pct": summary.meme_exposure_pct,
                    "max_single_position_pct": summary.max_single_position_pct,
                    "open_positions_count": summary.open_positions_count,
                    "positions_df": pd.DataFrame(positions_data),
                    "raw_positions": summary.open_positions,
                }

        return run_async(_query())

    @classmethod
    def place_paper_order(
        cls,
        symbol: str,
        side: str,
        quantity: float,
        account_id: str = "default_paper",
        order_type: str = "MARKET",
    ) -> dict:
        """Place a virtual paper order with risk enforcement."""
        from src.paper.broker import PaperBroker
        from src.paper.models import OrderSubmitRequest, PaperOrderSide, PaperOrderType

        async def _order():
            cls.ensure_seeded_data()
            factory = get_session_factory()
            async with factory() as session:
                broker = PaperBroker()
                req = OrderSubmitRequest(
                    account_id=account_id,
                    symbol=symbol.upper(),
                    side=PaperOrderSide.BUY if side.upper() == "BUY" else PaperOrderSide.SELL,
                    order_type=PaperOrderType.MARKET if order_type.upper() == "MARKET" else PaperOrderType.LIMIT,
                    quantity=quantity,
                )
                res = await broker.submit_order(session, req)
                return {
                    "status": "SUCCESS",
                    "order_id": res.id,
                    "symbol": res.symbol,
                    "quantity": res.quantity,
                    "fill_price": res.fills[0].fill_price if res.fills else 0.0,
                }

        return run_async(_order())

    @classmethod
    def close_paper_position(cls, symbol: str, account_id: str = "default_paper") -> dict:
        """Close an open paper position completely."""
        from src.paper.broker import PaperBroker

        async def _close():
            cls.ensure_seeded_data()
            factory = get_session_factory()
            async with factory() as session:
                broker = PaperBroker()
                pos = await broker.close_position(session, account_id=account_id, symbol=symbol)
                return {
                    "status": "SUCCESS",
                    "symbol": pos.symbol,
                    "realized_pnl": pos.realized_pnl,
                }

        return run_async(_close())

    @classmethod
    def reset_paper_account(cls, account_id: str = "default_paper", starting_balance: float = 100000.0) -> dict:
        """Reset virtual paper account balance."""
        from src.paper.broker import PaperBroker

        async def _reset():
            cls.ensure_seeded_data()
            factory = get_session_factory()
            async with factory() as session:
                broker = PaperBroker()
                acc = await broker.reset_account(session, account_id=account_id, starting_balance=starting_balance)
                return {"status": "SUCCESS", "cash_balance": acc.cash_balance}

        return run_async(_reset())
