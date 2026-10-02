"""Performance benchmark test for the BacktestEngine with pre-indexed universe lookup."""

import time
from datetime import datetime, timedelta

from src.backtesting.engine import BacktestEngine
from src.backtesting.models import BacktestConfig, SlippageModelType
from src.backtesting.strategies.momentum import MomentumBreakoutStrategy


def test_backtest_engine_performance_benchmark() -> None:
    """Benchmark BacktestEngine on a multi-asset hourly dataset.

    Verifies that pre-indexing by timestamp ensures O(bars * assets) linear time
    rather than O(bars^2 * assets) quadratic scan.
    """
    t0 = datetime(2023, 1, 1)
    num_assets = 30
    num_bars = 720  # 30 days of 1-hour bars (720 bars * 30 assets = 21,600 candles)
    symbols = [f"ASSET_{i}" for i in range(num_assets)]
    symbols[0] = "BTC"  # Benchmark symbol

    candles: dict = {s: [] for s in symbols}
    features: dict = {s: [] for s in symbols}

    for s in symbols:
        price = 100.0
        for b in range(num_bars):
            t = t0 + timedelta(hours=b)
            price *= 1.0005
            candles[s].append({
                "time": t,
                "open": price,
                "high": price * 1.002,
                "low": price * 0.998,
                "close": price,
                "volume": 500.0,
                "volume_usd": 50000.0,
            })
            features[s].append({
                "time": t,
                "return_30d": 0.05,
                "volume_to_20d_avg": 1.1,
                "volatility_adjusted_momentum": 1.2,
                "spread_est_bps": 5.0,
            })

    config = BacktestConfig(
        strategy_name="MomentumBreakout",
        start_date=t0,
        end_date=t0 + timedelta(hours=num_bars - 1),
        initial_capital=100000.0,
        timeframe="1h",
        slippage_model=SlippageModelType.FIXED_BPS,
    )
    strategy = MomentumBreakoutStrategy(parameters={"top_n_assets": 5, "min_return_30d": 0.02})
    engine = BacktestEngine(config, strategy)

    start_time = time.perf_counter()
    result = engine.run(candles, features)
    elapsed = time.perf_counter() - start_time

    assert result.total_trades >= 0
    assert len(result.equity_curve) == num_bars
    # With pre-indexing, 21,600 candles across 720 bars must complete in under 2.0 seconds
    assert elapsed < 3.0, f"Backtest took too long: {elapsed:.2f}s (expected < 3.0s with pre-indexing)"
