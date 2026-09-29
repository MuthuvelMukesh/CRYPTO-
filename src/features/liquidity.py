"""Liquidity and transaction friction proxy calculations."""

from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel


class LiquidityMetrics(BaseModel):
    """Calculated liquidity, spread, and market depth proxies."""
    spread_est_bps: float | None = None
    bid_ask_spread_bps: float | None = None
    slippage_proxy_10k_bps: float | None = None
    volume_to_depth_ratio: float | None = None


def estimate_corwin_schultz_spread(
    highs: Sequence[float],
    lows: Sequence[float],
) -> float | None:
    """
    Estimate bid-ask spread from high and low prices using Corwin & Schultz (2012).
    Returns estimated spread in basis points (bps).
    """
    highs_arr = np.array(highs, dtype=np.float64)
    lows_arr = np.array(lows, dtype=np.float64)
    n = len(highs_arr)
    if n < 4:
        return None

    # Filter invalid
    valid = (highs_arr > 0) & (lows_arr > 0) & (highs_arr >= lows_arr)
    highs_arr = highs_arr[valid]
    lows_arr = lows_arr[valid]
    if len(highs_arr) < 4:
        return None

    # 2-day high/low
    gamma = (np.log(np.maximum(highs_arr[1:], highs_arr[:-1]) / np.minimum(lows_arr[1:], lows_arr[:-1]))) ** 2
    beta = (np.log(highs_arr[1:] / lows_arr[1:])) ** 2 + (np.log(highs_arr[:-1] / lows_arr[:-1])) ** 2

    denom = 3.0 - 2.0 * np.sqrt(2.0)
    alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / denom - np.sqrt(gamma / denom)

    # Average positive alpha
    alpha_pos = alpha[alpha > 0]
    if len(alpha_pos) == 0:
        return 5.0  # Baseline 5 bps minimum

    mean_alpha = np.mean(alpha_pos)
    spread = 2.0 * (np.exp(mean_alpha) - 1.0) / (1.0 + np.exp(mean_alpha))
    return float(max(1.0, min(1000.0, spread * 10000.0)))  # in bps, bounded [1, 1000]


def calculate_liquidity_features(
    highs: Sequence[float],
    lows: Sequence[float],
    volume_24h_usd: float | None = None,
    orderbook_spread_bps: float | None = None,
    orderbook_depth_usd: float | None = None,
) -> LiquidityMetrics:
    """Calculate effective spread proxy and estimated market impact."""
    # Estimated spread via Corwin-Schultz
    spread_est_bps = estimate_corwin_schultz_spread(highs[-20:], lows[-20:])

    if orderbook_spread_bps is not None and orderbook_spread_bps > 0:
        actual_spread = orderbook_spread_bps
    else:
        actual_spread = spread_est_bps or 5.0

    # Slippage proxy for $10,000 order: gamma * sqrt(order_size / vol_24h)
    slippage_10k: float | None = None
    if volume_24h_usd is not None and volume_24h_usd > 1000:
        # Market impact model parameter gamma ~ 100 bps
        impact = 100.0 * np.sqrt(10000.0 / volume_24h_usd)
        slippage_10k = float(min(500.0, max(1.0, impact)))

    vol_to_depth = None
    if volume_24h_usd is not None and orderbook_depth_usd is not None and orderbook_depth_usd > 0:
        vol_to_depth = float(volume_24h_usd / orderbook_depth_usd)

    return LiquidityMetrics(
        spread_est_bps=spread_est_bps,
        bid_ask_spread_bps=actual_spread,
        slippage_proxy_10k_bps=slippage_10k,
        volume_to_depth_ratio=vol_to_depth,
    )
