"""Vectorized momentum factor calculations."""

from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel


class MomentumMetrics(BaseModel):
    """Calculated momentum features for an asset at a single point in time."""
    return_1d: float | None = None
    return_3d: float | None = None
    return_7d: float | None = None
    return_14d: float | None = None
    return_30d: float | None = None
    return_90d: float | None = None
    momentum_acceleration: float | None = None
    volatility_adjusted_momentum: float | None = None


def calculate_momentum_features(
    prices: Sequence[float],
    candles_per_day: int = 24,  # e.g., 24 for 1h candles, 1 for 1d candles
) -> MomentumMetrics:
    """
    Calculate multi-horizon returns, acceleration, and volatility-adjusted momentum
    using strictly historical prices up to the current point in time.
    """
    arr = np.array(prices, dtype=np.float64)
    n = len(arr)
    if n < 2:
        return MomentumMetrics()

    current_price = arr[-1]
    if current_price <= 0:
        return MomentumMetrics()

    def get_return(lookback_days: int) -> float | None:
        idx = int(lookback_days * candles_per_day)
        if n > idx and arr[-idx - 1] > 0:
            return float((current_price / arr[-idx - 1]) - 1.0)
        return None

    r1 = get_return(1)
    r3 = get_return(3)
    r7 = get_return(7)
    r14 = get_return(14)
    r30 = get_return(30)
    r90 = get_return(90)

    # Momentum Acceleration: 7D return today minus 7D return 7 days ago
    acceleration: float | None = None
    lag7_idx = int(7 * candles_per_day)
    lag14_idx = int(14 * candles_per_day)
    if n > lag14_idx and arr[-lag14_idx - 1] > 0 and arr[-lag7_idx - 1] > 0:
        prior_r7 = (arr[-lag7_idx - 1] / arr[-lag14_idx - 1]) - 1.0
        if r7 is not None:
            acceleration = float(r7 - prior_r7)

    # Volatility-adjusted momentum (30-day return / 30-day realized volatility)
    vol_adj_mom: float | None = None
    lookback_30 = int(30 * candles_per_day)
    if n > lookback_30 and r30 is not None:
        slice_30 = arr[-lookback_30:]
        pct_changes = np.diff(slice_30) / slice_30[:-1]
        std = np.std(pct_changes, ddof=1)
        if std > 1e-6 and not np.isnan(std):
            # Annualize standard deviation
            annualized_vol = std * np.sqrt(365.25 * candles_per_day)
            vol_adj_mom = float(r30 / annualized_vol)

    return MomentumMetrics(
        return_1d=r1,
        return_3d=r3,
        return_7d=r7,
        return_14d=r14,
        return_30d=r30,
        return_90d=r90,
        momentum_acceleration=acceleration,
        volatility_adjusted_momentum=vol_adj_mom,
    )
