"""Vectorized relative strength factor calculations against BTC, ETH, and sector benchmarks."""

from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel


class RelativeStrengthMetrics(BaseModel):
    """Calculated relative strength factors against benchmarks."""
    rs_btc_1d: float | None = None
    rs_btc_7d: float | None = None
    rs_btc_30d: float | None = None
    rs_eth_30d: float | None = None
    rs_sector_30d: float | None = None
    rs_ratio_above_ema50: bool | None = None


def calculate_ema(series: np.ndarray, period: int) -> np.ndarray:
    """Calculate Exponential Moving Average over a 1D array."""
    if len(series) < period:
        return np.full_like(series, np.nan)
    alpha = 2.0 / (period + 1.0)
    ema = np.empty_like(series)
    ema[0] = series[0]
    for i in range(1, len(series)):
        ema[i] = alpha * series[i] + (1.0 - alpha) * ema[i - 1]
    return ema


def calculate_relative_strength(
    asset_prices: Sequence[float],
    btc_prices: Sequence[float] | None = None,
    eth_prices: Sequence[float] | None = None,
    sector_prices: Sequence[float] | None = None,
    candles_per_day: int = 24,
) -> RelativeStrengthMetrics:
    """
    Calculate excess return of asset over benchmarks:
    RS = Return_asset - Return_benchmark
    """
    a_arr = np.array(asset_prices, dtype=np.float64)
    n = len(a_arr)
    if n < 2:
        return RelativeStrengthMetrics()

    def get_excess_return(benchmark: Sequence[float] | None, days: int) -> float | None:
        if benchmark is None:
            return None
        b_arr = np.array(benchmark, dtype=np.float64)
        if len(b_arr) != n:
            return None

        idx = int(days * candles_per_day)
        if n > idx and a_arr[-idx - 1] > 0 and b_arr[-idx - 1] > 0 and b_arr[-1] > 0:
            asset_ret = (a_arr[-1] / a_arr[-idx - 1]) - 1.0
            bench_ret = (b_arr[-1] / b_arr[-idx - 1]) - 1.0
            return float(asset_ret - bench_ret)
        return None

    rs_btc_1d = get_excess_return(btc_prices, 1)
    rs_btc_7d = get_excess_return(btc_prices, 7)
    rs_btc_30d = get_excess_return(btc_prices, 30)
    rs_eth_30d = get_excess_return(eth_prices, 30)
    rs_sector_30d = get_excess_return(sector_prices, 30)

    # Relative ratio trend vs BTC: ratio = asset / btc > EMA50(ratio)
    ratio_above_ema: bool | None = None
    if btc_prices is not None:
        b_arr = np.array(btc_prices, dtype=np.float64)
        if len(b_arr) == n and np.all(b_arr > 0):
            ratio = a_arr / b_arr
            lookback_ema = min(len(ratio), int(50 * candles_per_day))
            if lookback_ema >= 50:
                ema = calculate_ema(ratio[-lookback_ema:], 50)
                if not np.isnan(ema[-1]):
                    ratio_above_ema = bool(ratio[-1] > ema[-1])

    return RelativeStrengthMetrics(
        rs_btc_1d=rs_btc_1d,
        rs_btc_7d=rs_btc_7d,
        rs_btc_30d=rs_btc_30d,
        rs_eth_30d=rs_eth_30d,
        rs_sector_30d=rs_sector_30d,
        rs_ratio_above_ema50=ratio_above_ema,
    )
