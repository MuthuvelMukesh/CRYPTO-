"""Unit tests for walk-forward optimization and multi-metric evaluation."""

from datetime import datetime, timedelta

from src.backtesting.models import BacktestConfig, SlippageModelType
from src.backtesting.walk_forward import WalkForwardAnalyzer


def test_walk_forward_with_parameter_grid() -> None:
    t0 = datetime(2023, 1, 1)
    symbols = ["BTC", "ETH"]

    # 60 days of synthetic data
    candles: dict = {s: [] for s in symbols}
    features: dict = {s: [] for s in symbols}
    for s in symbols:
        price = 100.0
        for d in range(60):
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
                "return_30d": 0.15,
                "volume_to_20d_avg": 1.2,
                "volatility_adjusted_momentum": 1.8,
            })

    config = BacktestConfig(
        strategy_name="MomentumBreakout",
        start_date=t0,
        end_date=t0 + timedelta(days=59),
        initial_capital=100000.0,
        slippage_model=SlippageModelType.NONE,
    )

    param_grid = [
        {"top_n_assets": 1, "min_return_30d": 0.05},
        {"top_n_assets": 2, "min_return_30d": 0.10},
    ]

    analyzer = WalkForwardAnalyzer(
        base_config=config,
        windows_count=2,
        train_ratio=0.6,
        parameter_grid=param_grid,
        optimization_metric="sharpe_ratio",
    )
    report = analyzer.run_analysis(historical_candles=candles, historical_features=features)

    assert report.strategy_name == "MomentumBreakout"
    assert report.windows_count == 2
    assert len(report.windows) == 2

    # Check multi-metric fields
    assert hasattr(report, "mean_cagr_efficiency")
    assert hasattr(report, "mean_sharpe_efficiency")
    assert hasattr(report, "mean_drawdown_ratio")
    assert hasattr(report, "mean_train_sharpe")
    assert hasattr(report, "mean_test_sharpe")

    # Each window must record selected parameters
    for w in report.windows:
        assert "selected_parameters" in w
        assert w["selected_parameters"] in param_grid
        assert "sharpe_efficiency" in w
        assert "drawdown_ratio" in w
        assert "cagr_efficiency" in w
