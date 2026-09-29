"""Quantitative mathematical and statistical utilities."""

from collections.abc import Sequence

import numpy as np


def calculate_returns(prices: Sequence[float]) -> np.ndarray:
    """Calculate simple fractional returns from a sequence of prices."""
    arr = np.array(prices, dtype=np.float64)
    if len(arr) < 2:
        return np.array([], dtype=np.float64)
    return np.diff(arr) / arr[:-1]


def calculate_log_returns(prices: Sequence[float]) -> np.ndarray:
    """Calculate logarithmic returns from a sequence of prices."""
    arr = np.array(prices, dtype=np.float64)
    if len(arr) < 2:
        return np.array([], dtype=np.float64)
    return np.diff(np.log(arr))


def calculate_cagr(start_val: float, end_val: float, days: float) -> float:
    """Calculate Compound Annual Growth Rate (CAGR)."""
    if start_val <= 0 or end_val <= 0 or days <= 0:
        return 0.0
    years = days / 365.25
    return float((end_val / start_val) ** (1.0 / years) - 1.0)


def calculate_sharpe_ratio(
    returns: Sequence[float], risk_free_rate: float = 0.0, periods_per_year: int = 365
) -> float:
    """Calculate annualized Sharpe Ratio."""
    arr = np.array(returns, dtype=np.float64)
    if len(arr) < 2:
        return 0.0
    excess_returns = arr - (risk_free_rate / periods_per_year)
    std = np.std(excess_returns, ddof=1)
    if std == 0 or np.isnan(std):
        return 0.0
    return float(np.mean(excess_returns) / std * np.sqrt(periods_per_year))


def calculate_sortino_ratio(
    returns: Sequence[float],
    target_return: float = 0.0,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365,
) -> float:
    """Calculate annualized Sortino Ratio considering only downside volatility."""
    arr = np.array(returns, dtype=np.float64)
    if len(arr) < 2:
        return 0.0
    excess_returns = arr - (risk_free_rate / periods_per_year)
    downside_diff = np.minimum(0.0, arr - target_return)
    downside_std = np.sqrt(np.mean(downside_diff**2))
    if downside_std == 0 or np.isnan(downside_std):
        return 0.0
    return float(np.mean(excess_returns) / downside_std * np.sqrt(periods_per_year))


def calculate_max_drawdown(equity_curve: Sequence[float]) -> tuple[float, int, int]:
    """
    Calculate maximum drawdown percentage, peak index, and trough index.
    Returns: (max_drawdown_pct, peak_idx, trough_idx)
    """
    arr = np.array(equity_curve, dtype=np.float64)
    if len(arr) < 2:
        return 0.0, 0, 0

    peaks = np.maximum.accumulate(arr)
    drawdowns = (peaks - arr) / np.where(peaks > 0, peaks, 1.0)

    max_dd = float(np.max(drawdowns))
    trough_idx = int(np.argmax(drawdowns))
    peak_idx = int(np.argmax(arr[: trough_idx + 1])) if trough_idx > 0 else 0

    return max_dd * 100.0, peak_idx, trough_idx


def percentile_rank(value: float, series: Sequence[float]) -> float:
    """Calculate percentile rank of a value against a distribution (0 to 100)."""
    arr = np.array(series, dtype=np.float64)
    arr = arr[~np.isnan(arr)]
    if len(arr) == 0:
        return 50.0
    return float((np.sum(arr < value) + 0.5 * np.sum(arr == value)) / len(arr) * 100.0)
