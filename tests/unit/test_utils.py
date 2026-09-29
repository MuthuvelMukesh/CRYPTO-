"""Unit tests for time normalization and quantitative math functions."""

from datetime import UTC

import numpy as np

from src.utils.math import (
    calculate_max_drawdown,
    calculate_returns,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    percentile_rank,
)
from src.utils.time import to_utc_datetime, to_utc_ms, utc_now


def test_time_normalization():
    """Verify time utilities enforce UTC."""
    now = utc_now()
    assert now.tzinfo == UTC

    # From Unix milliseconds
    ms = 1700000000000
    dt_from_ms = to_utc_datetime(ms)
    assert dt_from_ms.tzinfo == UTC
    assert to_utc_ms(dt_from_ms) == ms

    # From ISO string with Z
    iso_str = "2024-01-01T12:00:00Z"
    dt_from_iso = to_utc_datetime(iso_str)
    assert dt_from_iso.tzinfo == UTC
    assert dt_from_iso.year == 2024


def test_quant_math_returns():
    """Verify return calculations."""
    prices = [100.0, 105.0, 102.0, 110.0]
    returns = calculate_returns(prices)
    assert len(returns) == 3
    assert np.isclose(returns[0], 0.05)
    assert np.isclose(returns[1], (102.0 - 105.0) / 105.0)


def test_quant_math_sharpe_and_sortino():
    """Verify Sharpe and Sortino ratio calculations."""
    # Positive series with mild volatility
    returns = [0.01, 0.02, -0.005, 0.015, 0.03, -0.01, 0.025]
    sharpe = calculate_sharpe_ratio(returns)
    sortino = calculate_sortino_ratio(returns)
    assert sharpe > 0
    assert sortino > 0
    # Sortino should penalize only downside, so with small downside it should be >= Sharpe
    assert sortino >= sharpe


def test_quant_math_max_drawdown():
    """Verify maximum drawdown computation."""
    equity = [100.0, 120.0, 90.0, 110.0, 80.0, 130.0]
    # Peak at 120, trough at 80 -> drawdown = (120 - 80) / 120 = 33.333%
    max_dd, peak_idx, trough_idx = calculate_max_drawdown(equity)
    assert np.isclose(max_dd, 33.333333, atol=1e-3)
    assert peak_idx == 1  # 120.0
    assert trough_idx == 4  # 80.0


def test_quant_math_percentile_rank():
    """Verify percentile ranking logic."""
    series = [10.0, 20.0, 30.0, 40.0, 50.0]
    rank_30 = percentile_rank(30.0, series)
    assert np.isclose(rank_30, 50.0)  # Middle element should be 50th percentile

    rank_lowest = percentile_rank(5.0, series)
    assert rank_lowest == 0.0

    rank_highest = percentile_rank(55.0, series)
    assert rank_highest == 100.0
