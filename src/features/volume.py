"""Vectorized volume expansion and turnover factor calculations."""

from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel


class VolumeMetrics(BaseModel):
    """Calculated volume expansion and turnover metrics."""
    volume_to_20_avg: float | None = None
    volume_to_7_avg: float | None = None
    volume_acceleration: float | None = None
    dollar_volume_24h: float | None = None
    turnover_ratio: float | None = None


def calculate_volume_features(
    volumes: Sequence[float],
    closes: Sequence[float],
    market_cap_usd: float | None = None,
    candles_per_day: int = 24,
) -> VolumeMetrics:
    """Calculate relative volume expansion, acceleration, and turnover."""
    v_arr = np.array(volumes, dtype=np.float64)
    c_arr = np.array(closes, dtype=np.float64)
    n = len(v_arr)
    if n < 20:
        return VolumeMetrics()

    last_vol = v_arr[-1]

    # RVOL 20
    avg20 = np.mean(v_arr[-20:])
    rvol20 = float(last_vol / avg20) if avg20 > 0 else None

    # RVOL 7 (assuming daily or 7 candles)
    avg7 = np.mean(v_arr[-7:])
    rvol7 = float(last_vol / avg7) if avg7 > 0 else None

    # Volume Acceleration: average volume over last 3 days vs prior 14 days
    vol_acc: float | None = None
    p3 = int(3 * candles_per_day)
    p14 = int(14 * candles_per_day)
    if n >= p14:
        mean_3d = np.mean(v_arr[-p3:])
        mean_14d = np.mean(v_arr[-p14:])
        if mean_14d > 0:
            vol_acc = float(mean_3d / mean_14d)

    # 24h Dollar Volume
    dollar_vol_24h: float | None = None
    p24 = min(n, candles_per_day)
    if p24 > 0:
        dollar_vol_24h = float(np.sum(v_arr[-p24:] * c_arr[-p24:]))

    # Turnover: 24h dollar volume / market cap
    turnover: float | None = None
    if dollar_vol_24h is not None and market_cap_usd is not None and market_cap_usd > 0:
        turnover = float(dollar_vol_24h / market_cap_usd)

    return VolumeMetrics(
        volume_to_20_avg=rvol20,
        volume_to_7_avg=rvol7,
        volume_acceleration=vol_acc,
        dollar_volume_24h=dollar_vol_24h,
        turnover_ratio=turnover,
    )
