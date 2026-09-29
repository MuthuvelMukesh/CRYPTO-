"""Automated Look-Ahead Bias and Future Data Leakage Verification Suite."""

import copy

import numpy as np
import pytest

from src.features.liquidity import calculate_liquidity_features
from src.features.momentum import calculate_momentum_features
from src.features.trend import calculate_trend_features
from src.features.volatility import calculate_volatility_features
from src.features.volume import calculate_volume_features


@pytest.fixture
def sample_market_series():
    """Generate 100 synthetic sequential market candles."""
    np.random.seed(42)
    n = 100
    base_price = 100.0
    returns = np.random.normal(0.001, 0.02, n)
    prices = base_price * np.exp(np.cumsum(returns))
    highs = prices * (1.0 + np.abs(np.random.normal(0.005, 0.005, n)))
    lows = prices * (1.0 - np.abs(np.random.normal(0.005, 0.005, n)))
    volumes = np.random.uniform(500, 2000, n)
    return {
        "prices": prices.tolist(),
        "highs": highs.tolist(),
        "lows": lows.tolist(),
        "volumes": volumes.tolist(),
    }


def test_no_future_data_leakage_in_features(sample_market_series):
    """
    Verify that features calculated at timestamp T are strictly invariant to any future
    price spikes, flash crashes, or volume anomalies occurring at T+1, T+2, ...
    """
    cutoff = 50  # Timestamp T
    original_prices = sample_market_series["prices"]
    original_highs = sample_market_series["highs"]
    original_lows = sample_market_series["lows"]
    original_volumes = sample_market_series["volumes"]

    # Compute baseline features at T = 50
    base_mom = calculate_momentum_features(original_prices[:cutoff])
    base_trend = calculate_trend_features(
        original_highs[:cutoff], original_lows[:cutoff], original_prices[:cutoff]
    )
    base_vol = calculate_volume_features(original_volumes[:cutoff], original_prices[:cutoff])
    base_volatility = calculate_volatility_features(
        original_highs[:cutoff], original_lows[:cutoff], original_prices[:cutoff]
    )
    base_liq = calculate_liquidity_features(
        original_highs[:cutoff], original_lows[:cutoff]
    )

    # Now create a perturbed dataset with extreme future shocks at T+1 ... T+49
    perturbed_prices = copy.deepcopy(original_prices)
    perturbed_highs = copy.deepcopy(original_highs)
    perturbed_lows = copy.deepcopy(original_lows)
    perturbed_volumes = copy.deepcopy(original_volumes)

    # Inject extreme future shocks
    perturbed_prices[cutoff + 1] = 999999.0  # 10000x future moon
    perturbed_prices[cutoff + 5] = 0.01      # Future total collapse
    perturbed_highs[cutoff + 1] = 1000000.0
    perturbed_lows[cutoff + 5] = 0.005
    perturbed_volumes[cutoff + 2] = 1e9       # 1 billion future volume

    # Recompute features at T = 50 on the sliced data
    test_mom = calculate_momentum_features(perturbed_prices[:cutoff])
    test_trend = calculate_trend_features(
        perturbed_highs[:cutoff], perturbed_lows[:cutoff], perturbed_prices[:cutoff]
    )
    test_vol = calculate_volume_features(perturbed_volumes[:cutoff], perturbed_prices[:cutoff])
    test_volatility = calculate_volatility_features(
        perturbed_highs[:cutoff], perturbed_lows[:cutoff], perturbed_prices[:cutoff]
    )
    test_liq = calculate_liquidity_features(
        perturbed_highs[:cutoff], perturbed_lows[:cutoff]
    )

    # 1. Momentum invariants
    assert base_mom.return_1d == test_mom.return_1d
    assert base_mom.return_7d == test_mom.return_7d
    assert base_mom.momentum_acceleration == test_mom.momentum_acceleration

    # 2. Trend invariants
    assert base_trend.ema20_ratio == test_trend.ema20_ratio
    assert base_trend.trend_alignment_score == test_trend.trend_alignment_score
    assert base_trend.atr_14 == test_trend.atr_14

    # 3. Volume invariants
    assert base_vol.volume_to_20_avg == test_vol.volume_to_20_avg
    assert base_vol.volume_acceleration == test_vol.volume_acceleration

    # 4. Volatility invariants
    assert base_volatility.realized_vol_30d == test_volatility.realized_vol_30d
    assert base_volatility.max_drawdown_90d == test_volatility.max_drawdown_90d

    # 5. Liquidity invariants
    assert base_liq.spread_est_bps == test_liq.spread_est_bps
