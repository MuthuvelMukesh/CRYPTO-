"""Unit tests for quantitative performance, risk, and attribution metrics."""

from datetime import datetime, timedelta

import pytest

from src.backtesting.metrics import (
    calculate_annualized_volatility,
    calculate_cagr,
    calculate_calmar_ratio,
    calculate_drawdown_series,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_trade_metrics,
    compute_complete_metrics,
)
from src.backtesting.models import BacktestTradeRecord, EquityPoint


def test_cagr_calculation() -> None:
    t0 = datetime(2023, 1, 1)
    t1 = datetime(2024, 1, 1)  # exactly 365 days

    # 100% gain over 1 year = 100% CAGR (within 365.25 day leap adjustment)
    cagr = calculate_cagr(100000.0, 200000.0, t0, t1)
    assert pytest.approx(cagr, rel=1e-2) == 100.0

    # 0% gain
    assert calculate_cagr(100000.0, 100000.0, t0, t1) == 0.0

    # 50% loss over 1 year
    cagr_loss = calculate_cagr(100000.0, 50000.0, t0, t1)
    assert pytest.approx(cagr_loss, rel=1e-2) == -50.0


def test_volatility_sharpe_and_sortino() -> None:
    # Daily returns: 10 days of positive 1%
    returns = [0.01] * 20
    vol = calculate_annualized_volatility(returns)
    assert vol == 0.0  # zero variance
    assert calculate_sharpe_ratio(returns) == 0.0

    # Alternating returns: +2%, -1%, +2%, -1%
    mixed_returns = [0.02, -0.01] * 15
    vol_mixed = calculate_annualized_volatility(mixed_returns)
    assert vol_mixed > 0.0

    sharpe = calculate_sharpe_ratio(mixed_returns, risk_free_rate=0.0)
    assert sharpe > 0.0

    sortino = calculate_sortino_ratio(mixed_returns, risk_free_rate=0.0)
    assert sortino > 0.0
    # Since upside is larger than downside, Sortino should be higher than Sharpe
    assert sortino >= sharpe


def test_max_drawdown_and_drawdown_series() -> None:
    equities = [100.0, 120.0, 150.0, 120.0, 90.0, 110.0, 160.0]
    # Peak is 150, trough is 90 -> (150 - 90) / 150 = 40%
    max_dd, peak_idx, trough_idx = calculate_max_drawdown(equities)
    assert max_dd == 40.0
    assert peak_idx == 2  # 150.0
    assert trough_idx == 4  # 90.0

    dd_series = calculate_drawdown_series(equities)
    assert len(dd_series) == len(equities)
    assert dd_series[0] == 0.0
    assert dd_series[2] == 0.0
    assert pytest.approx(dd_series[4], rel=1e-3) == -40.0
    assert dd_series[6] == 0.0  # New peak 160


def test_calmar_ratio() -> None:
    cagr = 30.0
    max_dd = 15.0
    calmar = calculate_calmar_ratio(cagr, max_dd)
    assert calmar == 2.0

    # Zero drawdown safe guard
    assert calculate_calmar_ratio(25.0, 0.0) == 25.0


def test_trade_metrics_and_edge_cases() -> None:
    # Empty trades list
    empty_stats = calculate_trade_metrics([])
    assert empty_stats["total_trades"] == 0.0
    assert empty_stats["win_rate"] == 0.0
    assert empty_stats["profit_factor"] == 0.0

    # 4 trades: 3 wins (+100, +200, +150), 1 loss (-150)
    trades = [
        BacktestTradeRecord(
            trade_id="1", asset_id="BTC", entry_time=datetime(2023, 1, 1),
            exit_time=datetime(2023, 1, 2), entry_price=100.0, exit_price=110.0,
            quantity=10.0, pnl_usd=100.0, pnl_pct=10.0,
        ),
        BacktestTradeRecord(
            trade_id="2", asset_id="ETH", entry_time=datetime(2023, 1, 2),
            exit_time=datetime(2023, 1, 3), entry_price=100.0, exit_price=120.0,
            quantity=10.0, pnl_usd=200.0, pnl_pct=20.0,
        ),
        BacktestTradeRecord(
            trade_id="3", asset_id="SOL", entry_time=datetime(2023, 1, 3),
            exit_time=datetime(2023, 1, 4), entry_price=100.0, exit_price=115.0,
            quantity=10.0, pnl_usd=150.0, pnl_pct=15.0,
        ),
        BacktestTradeRecord(
            trade_id="4", asset_id="AVAX", entry_time=datetime(2023, 1, 4),
            exit_time=datetime(2023, 1, 5), entry_price=100.0, exit_price=85.0,
            quantity=10.0, pnl_usd=-150.0, pnl_pct=-15.0,
        ),
    ]

    stats = calculate_trade_metrics(trades)
    assert stats["total_trades"] == 4.0
    assert stats["winning_trades"] == 3.0
    assert stats["losing_trades"] == 1.0
    assert stats["win_rate"] == 75.0
    # Gross profit = 450, gross loss = 150 -> profit factor = 3.0
    assert stats["profit_factor"] == 3.0
    assert stats["total_pnl_usd"] == 300.0
    assert stats["avg_win_usd"] == 150.0
    assert stats["avg_loss_usd"] == 150.0


def test_complete_metrics_aggregation() -> None:
    t0 = datetime(2023, 1, 1)
    curve = [
        EquityPoint(time=t0 + timedelta(days=i), equity=100000.0 + (i * 1000.0), cash=10000.0,
                    positions_value=90000.0 + (i * 1000.0), drawdown_pct=0.0,
                    benchmark_equity=100000.0 + (i * 500.0))
        for i in range(30)
    ]
    trades = [
        BacktestTradeRecord(
            trade_id="1", asset_id="BTC", entry_time=t0, exit_time=t0 + timedelta(days=5),
            entry_price=100.0, exit_price=110.0, quantity=10.0, pnl_usd=100.0, pnl_pct=10.0,
        )
    ]

    metrics = compute_complete_metrics(curve, trades, t0, t0 + timedelta(days=29))
    assert metrics["initial_capital"] == 100000.0
    assert metrics["final_equity"] == 129000.0
    assert metrics["total_return_pct"] == 29.0
    assert metrics["benchmark_return_pct"] == 14.5
    assert metrics["excess_return_pct"] == 14.5
    assert metrics["total_trades"] == 1.0
    assert metrics["win_rate"] == 100.0
