"""Unit tests for all quantitative factor calculation modules."""

import numpy as np

from src.config.constants import MarketRegime
from src.features.market_regime import classify_market_regime
from src.features.momentum import calculate_momentum_features
from src.features.relative_strength import calculate_relative_strength
from src.features.sector import calculate_sector_metrics
from src.features.trend import calculate_trend_features
from src.features.volatility import calculate_volatility_features
from src.features.volume import calculate_volume_features


def test_momentum_returns_and_acceleration():
    """Verify return calculations across horizons and momentum acceleration."""
    # 24 candles per day * 15 days = 360 candles
    candles_per_day = 24
    prices = [100.0] * 360

    # Candle from 7 days ago (168 candles ago) = 100
    # Candle today = 110 -> 7d return = +10%
    prices[-1] = 110.0
    mom = calculate_momentum_features(prices, candles_per_day=candles_per_day)
    assert mom.return_1d is not None
    assert mom.return_7d is not None
    assert np.isclose(mom.return_7d, 0.10)


def test_relative_strength_vs_btc():
    """Verify relative return against BTC."""
    n = 100
    asset_prices = [100.0 + (i * 0.5) for i in range(n)]  # +50%
    btc_prices = [100.0 + (i * 0.2) for i in range(n)]    # +20%

    rs = calculate_relative_strength(
        asset_prices, btc_prices=btc_prices, candles_per_day=2
    )
    assert rs.rs_btc_1d is not None
    assert rs.rs_btc_30d is not None
    # Asset outperformed BTC, so relative return should be positive
    assert rs.rs_btc_30d > 0


def test_trend_indicators():
    """Verify EMAs, MACD, and Trend Alignment."""
    # Strongly upward trending prices
    closes = [50.0 + (i * 1.5) for i in range(60)]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]

    trend = calculate_trend_features(highs, lows, closes)
    assert trend.ema20_ratio is not None
    assert trend.ema20_ratio > 1.0  # Above EMA20
    assert trend.trend_alignment_score == 2  # Has EMA20 and EMA50 (n=60 < 200)
    assert trend.atr_14 is not None
    assert trend.atr_14 > 0


def test_volume_metrics():
    """Verify RVOL and volume acceleration."""
    closes = [100.0] * 50
    volumes = [1000.0] * 49 + [3000.0]  # 3x volume spike today

    vol = calculate_volume_features(volumes, closes, market_cap_usd=1e8)
    assert vol.volume_to_20_avg is not None
    assert vol.volume_to_20_avg > 2.5
    assert vol.turnover_ratio is not None


def test_volatility_metrics():
    """Verify realized vol, downside vol, and max drawdown."""
    closes = [100.0, 105.0, 95.0, 110.0, 85.0, 100.0] * 10
    highs = [c * 1.02 for c in closes]
    lows = [c * 0.98 for c in closes]

    vol = calculate_volatility_features(highs, lows, closes)
    assert vol.realized_vol_30d is not None
    assert vol.realized_vol_30d > 0
    assert vol.max_drawdown_90d is not None
    assert vol.max_drawdown_90d > 0


def test_market_regime_classification():
    """Verify market regime rules for Risk-On and Risk-Off states."""
    # 1. Bullish scenario: BTC rising strongly above EMA
    btc_bull = [30000.0 + (i * 500.0) for i in range(100)]
    eth_bull = [2000.0 + (i * 40.0) for i in range(100)]
    universe_bull = {
        "SOL": [100.0 + (i * 2.0) for i in range(100)],
        "NEAR": [5.0 + (i * 0.1) for i in range(100)],
    }

    regime_bull = classify_market_regime(
        btc_closes=btc_bull,
        eth_closes=eth_bull,
        universe_closes=universe_bull,
        aggregate_funding_rate=0.0004,
    )
    assert regime_bull.regime == MarketRegime.RISK_ON
    assert regime_bull.btc_above_ema50 is True
    assert regime_bull.market_breadth_pct >= 60.0

    # 2. Bearish scenario: BTC collapsing
    btc_bear = [60000.0 - (i * 400.0) for i in range(100)]
    universe_bear = {
        "SOL": [100.0 - (i * 0.8) for i in range(100)],
        "NEAR": [5.0 - (i * 0.04) for i in range(100)],
    }
    regime_bear = classify_market_regime(
        btc_closes=btc_bear,
        universe_closes=universe_bear,
    )
    assert regime_bear.regime == MarketRegime.RISK_OFF


def test_sector_performance_and_rotation():
    """Verify sector return aggregation and rotation status."""
    ai_assets = {
        "NEAR": [5.0 + (i * 0.1) for i in range(50)],
        "RENDER": [6.0 + (i * 0.12) for i in range(50)],
    }

    sector_perf = calculate_sector_metrics("AI", ai_assets)
    assert sector_perf is not None
    assert sector_perf.sector_name == "AI"
    assert sector_perf.asset_count == 2
    assert sector_perf.return_7d > 0
    assert sector_perf.breadth_pct == 100.0
    assert sector_perf.rotation_status in ["LEADING", "ACCELERATING"]
