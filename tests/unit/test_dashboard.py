"""Unit tests for Streamlit Dashboard components, charts, and data layer."""

import pandas as pd

from apps.dashboard.components.charts import (
    create_candlestick_chart,
    create_factor_radar_chart,
    create_sector_rotation_chart,
)
from apps.dashboard.data_layer import DashboardDataLayer


def test_dashboard_data_layer_scanner():
    """Verify DashboardDataLayer returns populated scanner DataFrame."""
    df = DashboardDataLayer.get_scanner_data()
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "Symbol" in df.columns
    assert "Opportunity" in df.columns
    assert "Class" in df.columns
    assert "Momentum" in df.columns
    assert "Relative Strength" in df.columns
    assert len(df) >= 8


def test_dashboard_data_layer_regime_and_candles():
    """Verify DashboardDataLayer returns regime status and candlestick series."""
    regime = DashboardDataLayer.get_market_regime()
    assert isinstance(regime, dict)
    assert "regime" in regime
    assert "confidence" in regime

    candles = DashboardDataLayer.get_candlestick_data("BTC")
    assert isinstance(candles, pd.DataFrame)
    assert not candles.empty
    assert "close" in candles.columns
    assert "volume" in candles.columns


def test_plotly_chart_generators():
    """Verify Plotly chart creation without error."""
    candles = DashboardDataLayer.get_candlestick_data("BTC")
    fig_candle = create_candlestick_chart(candles, "BTC")
    assert fig_candle is not None
    assert len(fig_candle.data) >= 3  # Candlestick + EMA20 + EMA50 + Volume

    scores = {
        "Momentum": 75.0,
        "Relative Strength": 80.0,
        "Trend": 70.0,
        "Volume": 65.0,
        "Liquidity": 85.0,
        "Quality": 78.0,
        "Risk": 60.0,
    }
    fig_radar = create_factor_radar_chart(scores, "BTC")
    assert fig_radar is not None
    assert len(fig_radar.data) >= 1

    sector_df = pd.DataFrame([
        {"sector_name": "L1", "return_7d": 0.08, "return_1d": 0.02, "rotation_status": "LEADING"},
        {"sector_name": "DeFi", "return_7d": -0.02, "return_1d": 0.01, "rotation_status": "WEAKENING"},
    ])
    fig_sector = create_sector_rotation_chart(sector_df)
    assert fig_sector is not None
    assert len(fig_sector.data) == 2


def test_dashboard_backtest_integration():
    """Verify DashboardDataLayer executes backtest and creates interactive equity/drawdown charts."""
    from apps.dashboard.components.charts import (
        create_equity_curve_chart,
        create_underwater_drawdown_chart,
    )

    bt_res = DashboardDataLayer.run_backtest(
        strategy_name="MomentumBreakout",
        initial_capital=50000.0,
        days=30,
        slippage_model="fixed_bps",
    )
    assert bt_res is not None
    assert "metrics" in bt_res
    assert "cagr" in bt_res["metrics"]
    assert "equity_df" in bt_res
    assert not bt_res["equity_df"].empty

    fig_equity = create_equity_curve_chart(bt_res["equity_df"], "MomentumBreakout")
    assert fig_equity is not None
    assert len(fig_equity.data) >= 1

    fig_dd = create_underwater_drawdown_chart(bt_res["equity_df"])
    assert fig_dd is not None
    assert len(fig_dd.data) >= 1
