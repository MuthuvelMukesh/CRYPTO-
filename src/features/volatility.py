"""Vectorized volatility and downside risk factor calculations."""

from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel

from src.utils.math import calculate_max_drawdown


class VolatilityMetrics(BaseModel):
    """Calculated volatility and downside risk metrics."""
    realized_vol_30d: float | None = None
    downside_vol_30d: float | None = None
    max_drawdown_90d: float | None = None
    rolling_std_20: float | None = None
    parkinson_vol_30d: float | None = None


def calculate_volatility_features(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    candles_per_day: int = 24,
) -> VolatilityMetrics:
    """Calculate realized volatility, downside deviation, and maximum drawdown."""
    c_arr = np.array(closes, dtype=np.float64)
    h_arr = np.array(highs, dtype=np.float64)
    l_arr = np.array(lows, dtype=np.float64)
    n = len(c_arr)
    if n < 20:
        return VolatilityMetrics()

    # Returns
    returns = np.diff(c_arr) / c_arr[:-1]

    # Rolling 20-period standard deviation
    rolling_std_20 = float(np.std(returns[-20:], ddof=1)) if len(returns) >= 20 else None

    # Realized Volatility 30D (annualized)
    p30 = min(len(returns), int(30 * candles_per_day))
    realized_vol_30d: float | None = None
    downside_vol_30d: float | None = None
    parkinson_vol_30d: float | None = None

    if p30 >= 20:
        slice_ret = returns[-p30:]
        std_30 = np.std(slice_ret, ddof=1)
        annual_factor = np.sqrt(365.25 * candles_per_day)
        realized_vol_30d = float(std_30 * annual_factor)

        # Downside Volatility
        neg_ret = slice_ret[slice_ret < 0]
        if len(neg_ret) > 0:
            downside_std = np.sqrt(np.mean(neg_ret**2))
            downside_vol_30d = float(downside_std * annual_factor)

        # Parkinson Volatility using High/Low (30D)
        h_slice = h_arr[-p30:]
        l_slice = l_arr[-p30:]
        valid_mask = (h_slice > 0) & (l_slice > 0) & (h_slice >= l_slice)
        if np.sum(valid_mask) > 10:
            log_hl = np.log(h_slice[valid_mask] / l_slice[valid_mask])
            park_var = (1.0 / (4.0 * np.log(2.0))) * np.mean(log_hl**2)
            parkinson_vol_30d = float(np.sqrt(park_var) * annual_factor)

    # Maximum Drawdown over last 90 days
    p90 = min(n, int(90 * candles_per_day))
    max_dd_90d: float | None = None
    if p90 >= 20:
        max_dd, _, _ = calculate_max_drawdown(c_arr[-p90:])
        max_dd_90d = float(max_dd)

    return VolatilityMetrics(
        realized_vol_30d=realized_vol_30d,
        downside_vol_30d=downside_vol_30d,
        max_drawdown_90d=max_dd_90d,
        rolling_std_20=rolling_std_20,
        parkinson_vol_30d=parkinson_vol_30d,
    )
