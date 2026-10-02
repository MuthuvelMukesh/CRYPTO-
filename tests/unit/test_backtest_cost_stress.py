"""Unit tests for cost stress testing helper."""

from datetime import datetime, timedelta

from src.backtesting.cost_stress import CostStressScenario, run_cost_stress_test
from src.backtesting.engine import BacktestEngine
from src.backtesting.models import BacktestConfig, SlippageModelType
from src.backtesting.strategies.momentum import MomentumBreakoutStrategy


def test_run_cost_stress_test() -> None:
    t0 = datetime(2023, 1, 1)
    symbols = ["BTC", "ETH"]

    # Generate 30 days of synthetic candles
    candles: dict = {s: [] for s in symbols}
    features: dict = {s: [] for s in symbols}
    for s in symbols:
        price = 100.0
        for d in range(30):
            t = t0 + timedelta(days=d)
            price *= 1.01
            candles[s].append({
                "time": t,
                "open": price * 0.99,
                "high": price * 1.02,
                "low": price * 0.98,
                "close": price,
                "volume": 1000.0,
                "volume_usd": 100000.0,
            })
            features[s].append({
                "time": t,
                "return_30d": 0.20,
                "volume_to_20d_avg": 1.5,
                "volatility_adjusted_momentum": 2.0,
                "spread_est_bps": 10.0,
                "atr_14_pct": 2.0,
            })

    config = BacktestConfig(
        strategy_name="MomentumBreakout",
        start_date=t0,
        end_date=t0 + timedelta(days=29),
        initial_capital=100000.0,
        maker_fee_bps=2.0,
        taker_fee_bps=5.0,
        slippage_model=SlippageModelType.FIXED_BPS,
        fixed_slippage_bps=5.0,
    )
    strategy = MomentumBreakoutStrategy(parameters={"top_n_assets": 1, "min_return_30d": 0.05})
    engine = BacktestEngine(config, strategy)

    scenarios = run_cost_stress_test(
        engine=engine,
        historical_candles=candles,
        historical_features=features,
        multipliers=[1.0, 2.0, 3.0],
    )

    assert len(scenarios) == 3
    assert [s.multiplier for s in scenarios] == [1.0, 2.0, 3.0]
    assert all(isinstance(s, CostStressScenario) for s in scenarios)

    # As costs increase from 1x to 3x, fees and slippage must strictly increase
    assert scenarios[0].total_fees_usd <= scenarios[1].total_fees_usd <= scenarios[2].total_fees_usd
    assert scenarios[0].total_slippage_usd <= scenarios[1].total_slippage_usd <= scenarios[2].total_slippage_usd

    # Scenarios must convert cleanly to dict table rows
    table_rows = [s.to_dict() for s in scenarios]
    assert all("multiplier" in r and "total_return_pct" in r and "net_pnl_usd" in r for r in table_rows)
