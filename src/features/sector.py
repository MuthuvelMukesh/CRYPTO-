"""Sector performance aggregation, breadth, and rotation analysis."""

from collections.abc import Mapping, Sequence

import numpy as np
from pydantic import BaseModel


class SectorPerformance(BaseModel):
    """Calculated performance and rotation statistics for a single crypto sector."""
    sector_name: str
    asset_count: int
    return_1d: float
    return_7d: float
    return_30d: float
    breadth_pct: float  # % of coins in sector with positive 7D return
    volume_change_7d_pct: float
    rotation_status: str  # LEADING, ACCELERATING, WEAKENING, DECLINING


def calculate_sector_metrics(
    sector_name: str,
    asset_closes: Mapping[str, Sequence[float]],
    asset_volumes: Mapping[str, Sequence[float]] | None = None,
    candles_per_day: int = 24,
) -> SectorPerformance | None:
    """Calculate aggregated sector return, breadth, and rotation status."""
    if not asset_closes:
        return None

    p1 = int(1 * candles_per_day)
    p7 = int(7 * candles_per_day)
    p30 = int(30 * candles_per_day)

    r1_list: list[float] = []
    r7_list: list[float] = []
    r30_list: list[float] = []
    vol_curr_list: list[float] = []
    vol_prior_list: list[float] = []

    for sym, closes in asset_closes.items():
        arr = np.array(closes, dtype=np.float64)
        n = len(arr)
        if n < 2:
            continue

        eff_p1 = min(n - 1, p1)
        eff_p7 = min(n - 1, p7)
        eff_p30 = min(n - 1, p30)

        if eff_p1 > 0 and arr[-eff_p1 - 1] > 0:
            r1_list.append((arr[-1] / arr[-eff_p1 - 1]) - 1.0)
        if eff_p7 > 0 and arr[-eff_p7 - 1] > 0:
            r7_list.append((arr[-1] / arr[-eff_p7 - 1]) - 1.0)
        if eff_p30 > 0 and arr[-eff_p30 - 1] > 0:
            r30_list.append((arr[-1] / arr[-eff_p30 - 1]) - 1.0)

        if asset_volumes and sym in asset_volumes:
            v_arr = np.array(asset_volumes[sym], dtype=np.float64)
            if len(v_arr) > eff_p7 * 2 and eff_p7 > 0:
                vol_curr_list.append(np.sum(v_arr[-eff_p7:]))
                vol_prior_list.append(np.sum(v_arr[-eff_p7 * 2 : -eff_p7]))

    if not r7_list:
        return None

    mean_r1 = float(np.mean(r1_list)) if r1_list else 0.0
    mean_r7 = float(np.mean(r7_list))
    mean_r30 = float(np.mean(r30_list)) if r30_list else 0.0

    breadth = float((np.sum(np.array(r7_list) > 0) / len(r7_list)) * 100.0)

    vol_change = 0.0
    if vol_curr_list and vol_prior_list:
        total_curr = np.sum(vol_curr_list)
        total_prior = np.sum(vol_prior_list)
        if total_prior > 0:
            vol_change = float((total_curr - total_prior) / total_prior * 100.0)

    # Rotation classification
    if mean_r7 > 0.05 and mean_r1 > 0.01:
        status = "ACCELERATING"
    elif mean_r7 > 0.0:
        status = "LEADING"
    elif mean_r7 < -0.05 and mean_r1 > 0.0:
        status = "WEAKENING"
    else:
        status = "DECLINING"

    return SectorPerformance(
        sector_name=sector_name,
        asset_count=len(asset_closes),
        return_1d=round(mean_r1, 4),
        return_7d=round(mean_r7, 4),
        return_30d=round(mean_r30, 4),
        breadth_pct=round(breadth, 1),
        volume_change_7d_pct=round(vol_change, 2),
        rotation_status=status,
    )
