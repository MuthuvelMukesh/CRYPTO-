"""Integration tests for backtesting pipeline, persistence, REST APIs, and walk-forward analysis."""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backtesting.models import BacktestConfig, SlippageModelType
from src.backtesting.walk_forward import WalkForwardAnalyzer
from src.database.models import Backtest, BacktestTrade
from src.ingestion.pipeline import seed_default_universe


@pytest.mark.asyncio
async def test_backtest_api_endpoints_and_persistence(client: AsyncClient, db_session: AsyncSession) -> None:
    """Verify strategy listing, running a backtest via REST, and retrieving results."""
    await seed_default_universe(db_session, exchange_id="binance")

    # 1. Test GET /api/v1/backtests/strategies
    res_strat = await client.get("/api/v1/backtests/strategies")
    assert res_strat.status_code == 200
    strat_list = res_strat.json()
    assert len(strat_list) >= 4
    strat_names = {s["name"] for s in strat_list}
    assert "MomentumBreakout" in strat_names
    assert "TrendRegimeFilter" in strat_names

    # 2. Test POST /api/v1/backtests/run
    start_t = datetime(2023, 1, 1)
    end_t = start_t + timedelta(days=60)
    payload = {
        "strategy_name": "MomentumBreakout",
        "symbols": ["BTC", "ETH", "SOL", "AVAX"],
        "start_date": start_t.isoformat(),
        "end_date": end_t.isoformat(),
        "initial_capital": 100000.0,
        "maker_fee_bps": 2.0,
        "taker_fee_bps": 5.0,
        "slippage_model": "market_impact",
        "parameters": {"top_n_assets": 2, "min_return_30d": 0.01},
    }

    res_run = await client.post("/api/v1/backtests/run", json=payload)
    assert res_run.status_code == 200, res_run.text
    run_data = res_run.json()
    backtest_id = run_data["id"]
    assert run_data["strategy_name"] == "MomentumBreakout"
    assert "metrics" in run_data
    assert "cagr" in run_data["metrics"]
    assert "sharpe_ratio" in run_data["metrics"]
    assert "trades" in run_data

    # 3. Test Database Persistence
    stmt = select(Backtest).where(Backtest.id == backtest_id)
    res_db = await db_session.execute(stmt)
    saved_bt = res_db.scalars().first()
    assert saved_bt is not None
    assert saved_bt.strategy_name == "MomentumBreakout"

    stmt_trades = select(BacktestTrade).where(BacktestTrade.backtest_id == backtest_id)
    res_trades = await db_session.execute(stmt_trades)
    saved_trades = res_trades.scalars().all()
    assert len(saved_trades) == len(run_data["trades"])

    # 4. Test GET /api/v1/backtests (list)
    res_list = await client.get("/api/v1/backtests")
    assert res_list.status_code == 200
    listed_runs = res_list.json()
    assert any(r["id"] == backtest_id for r in listed_runs)

    # 5. Test GET /api/v1/backtests/{backtest_id} (detail)
    res_detail = await client.get(f"/api/v1/backtests/{backtest_id}")
    assert res_detail.status_code == 200
    detail_data = res_detail.json()
    assert detail_data["id"] == backtest_id
    assert len(detail_data["trades"]) == len(saved_trades)


def test_walk_forward_analyzer_workflow() -> None:
    """Verify rolling walk-forward analysis runs and computes Walk-Forward Efficiency (WFE)."""
    t0 = datetime(2023, 1, 1)
    days = 120
    t_end = t0 + timedelta(days=days)

    import numpy as np

    np.random.seed(42)
    symbols = ["BTC", "ETH", "SOL"]
    candles = {}
    features = {}

    for sym in symbols:
        c_list = []
        f_list = []
        p = 100.0 if sym != "BTC" else 30000.0
        for d in range(days + 1):
            t = t0 + timedelta(days=d)
            ret = float(np.random.normal(0.002, 0.02))
            p_close = max(0.01, p * (1.0 + ret))
            c_list.append({
                "time": t, "open": p, "high": max(p, p_close) * 1.01,
                "low": min(p, p_close) * 0.99, "close": p_close,
                "volume": 1000.0, "volume_usd": 1000.0 * p_close,
            })
            f_list.append({
                "time": t, "return_30d": float(np.random.uniform(0.02, 0.15)),
                "volume_to_20d_avg": 1.2, "volatility_adjusted_momentum": 1.0,
                "ema20_ratio": 1.03, "ema50_ratio": 1.05, "adx_14": 25.0,
            })
            p = p_close
        candles[sym] = c_list
        features[sym] = f_list

    config = BacktestConfig(
        strategy_name="MomentumBreakout",
        start_date=t0,
        end_date=t_end,
        initial_capital=100000.0,
        slippage_model=SlippageModelType.NONE,
    )

    analyzer = WalkForwardAnalyzer(base_config=config, windows_count=3, train_ratio=0.6)
    report = analyzer.run_analysis(historical_candles=candles, historical_features=features)

    assert report.strategy_name == "MomentumBreakout"
    assert report.windows_count == 3
    assert len(report.windows) == 3
    assert isinstance(report.mean_efficiency_ratio, float)
    assert isinstance(report.is_overfit_suspected, bool)
