"""Pluggable position sizing algorithms and portfolio volatility governance for quantitative trading.

Supported models:
- FixedPercent / EqualWeight
- Volatility Targeting (inverse volatility parity)
- Fractional Kelly Criterion (risk-optimized capital growth)
- Portfolio Volatility Governor (cap aggregate portfolio risk)
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class BasePositionSizer(ABC):
    """Abstract base class for pluggable position sizing strategies."""

    def __init__(
        self,
        max_position_weight: float = 0.25,
        target_annual_vol: float = 0.20,
        kelly_fraction: float = 0.25,
    ) -> None:
        self.max_position_weight = max_position_weight
        self.target_annual_vol = target_annual_vol
        self.kelly_fraction = kelly_fraction

    @abstractmethod
    def calculate_weight(
        self,
        asset_id: str,
        signal_target_weight: float,
        portfolio_equity: float,
        asset_volatility_annual: float | None = None,
        win_rate: float | None = None,
        payoff_ratio: float | None = None,
        expected_excess_return: float | None = None,
    ) -> float:
        """Calculate target portfolio equity fraction for an asset (0.0 to max_position_weight)."""
        pass


class FixedPercentSizer(BasePositionSizer):
    """Standard fixed percentage / signal-directed position sizing."""

    def calculate_weight(
        self,
        asset_id: str,
        signal_target_weight: float,
        portfolio_equity: float,
        asset_volatility_annual: float | None = None,
        win_rate: float | None = None,
        payoff_ratio: float | None = None,
        expected_excess_return: float | None = None,
    ) -> float:
        weight = signal_target_weight if signal_target_weight > 0 else self.max_position_weight
        return min(max(0.0, weight), self.max_position_weight)


class VolatilityTargetSizer(BasePositionSizer):
    """Inverse volatility targeting: sizes positions to deliver a constant risk contribution.

    Formula:
        target_weight = target_annual_vol / max(floor_vol, asset_annual_vol)
        capped at max_position_weight.
    """

    def __init__(
        self,
        max_position_weight: float = 0.25,
        target_annual_vol: float = 0.20,
        floor_annual_vol: float = 0.10,
        **kwargs: Any,
    ) -> None:
        super().__init__(max_position_weight=max_position_weight, target_annual_vol=target_annual_vol)
        self.floor_annual_vol = floor_annual_vol

    def calculate_weight(
        self,
        asset_id: str,
        signal_target_weight: float,
        portfolio_equity: float,
        asset_volatility_annual: float | None = None,
        win_rate: float | None = None,
        payoff_ratio: float | None = None,
        expected_excess_return: float | None = None,
    ) -> float:
        vol = asset_volatility_annual if asset_volatility_annual is not None and asset_volatility_annual > 0 else 0.60
        vol = max(self.floor_annual_vol, vol)

        raw_weight = self.target_annual_vol / vol
        # Scale by signal confidence if signal_target_weight is provided
        scale = signal_target_weight / self.max_position_weight if signal_target_weight > 0 else 1.0
        weight = raw_weight * min(1.0, max(0.2, scale))
        return min(max(0.0, weight), self.max_position_weight)


class FractionalKellySizer(BasePositionSizer):
    """Fractional Kelly Criterion: optimizes long-term geometric compounding rate while limiting drawdown.

    Formula (discrete Bernoulli):
        f* = (p * b - (1 - p)) / b
        target_weight = kelly_fraction * max(0, f*)

    Continuous Gaussian alternative when expected_excess_return and vol are provided:
        f* = expected_excess_return / (vol^2)
    """

    def __init__(
        self,
        max_position_weight: float = 0.25,
        kelly_fraction: float = 0.25,
        default_win_rate: float = 0.55,
        default_payoff: float = 1.5,
        **kwargs: Any,
    ) -> None:
        super().__init__(max_position_weight=max_position_weight, kelly_fraction=kelly_fraction)
        self.default_win_rate = default_win_rate
        self.default_payoff = default_payoff

    def calculate_weight(
        self,
        asset_id: str,
        signal_target_weight: float,
        portfolio_equity: float,
        asset_volatility_annual: float | None = None,
        win_rate: float | None = None,
        payoff_ratio: float | None = None,
        expected_excess_return: float | None = None,
    ) -> float:
        # 1. Continuous Gaussian Kelly if return & vol available
        if expected_excess_return is not None and asset_volatility_annual is not None and asset_volatility_annual > 0:
            var = asset_volatility_annual**2
            continuous_kelly = expected_excess_return / var if var > 1e-4 else 0.0
            kelly_f = max(0.0, continuous_kelly)
        else:
            # 2. Discrete Bernoulli Kelly
            p = win_rate if win_rate is not None and 0.0 < win_rate < 1.0 else self.default_win_rate
            b = payoff_ratio if payoff_ratio is not None and payoff_ratio > 0.0 else self.default_payoff

            # f* = p - (1-p)/b
            full_kelly = p - ((1.0 - p) / b)
            kelly_f = max(0.0, full_kelly)

        weight = self.kelly_fraction * kelly_f
        return min(max(0.0, weight), self.max_position_weight)


class PortfolioVolatilityGovernor:
    """Monitors and constrains aggregate portfolio annualized volatility under a strict upper bound.

    Computes estimated portfolio volatility from active position weights and individual asset volatilities
    (assuming average cross-asset crypto correlation rho ~ 0.50). If aggregate portfolio vol exceeds the cap,
    scales down all weights proportionately.
    """

    def __init__(self, portfolio_vol_cap: float = 0.30, default_crypto_rho: float = 0.50) -> None:
        self.portfolio_vol_cap = portfolio_vol_cap
        self.default_crypto_rho = default_crypto_rho

    def estimate_portfolio_volatility(
        self,
        weights: dict[str, float],
        asset_vols: dict[str, float],
    ) -> float:
        """Estimate portfolio annualized volatility."""
        active = [k for k, w in weights.items() if w > 0]
        if not active:
            return 0.0

        n = len(active)
        if n == 1:
            k = active[0]
            return float(weights[k] * asset_vols.get(k, 0.60))

        # Vectorized portfolio variance: w' * Cov * w
        w_vec = np.array([weights[k] for k in active], dtype=np.float64)
        vol_vec = np.array([asset_vols.get(k, 0.60) for k in active], dtype=np.float64)

        # Construct correlation matrix with average pairwise correlation rho
        corr_matrix = np.full((n, n), self.default_crypto_rho, dtype=np.float64)
        np.fill_diagonal(corr_matrix, 1.0)

        cov_matrix = np.outer(vol_vec, vol_vec) * corr_matrix
        port_var = float(np.dot(w_vec, np.dot(cov_matrix, w_vec)))
        return float(math.sqrt(max(0.0, port_var)))

    def apply_cap(
        self,
        weights: dict[str, float],
        asset_vols: dict[str, float],
    ) -> tuple[dict[str, float], float, float]:
        """Scale down position weights if estimated portfolio volatility exceeds portfolio_vol_cap.

        Returns:
            (adjusted_weights, estimated_vol_before, scale_factor)
        """
        est_vol = self.estimate_portfolio_volatility(weights, asset_vols)
        if est_vol <= self.portfolio_vol_cap or est_vol <= 1e-6:
            return weights.copy(), est_vol, 1.0

        scale = self.portfolio_vol_cap / est_vol
        adjusted = {k: round(v * scale, 6) for k, v in weights.items()}
        return adjusted, est_vol, round(scale, 4)


def get_position_sizer(
    name: str = "fixed_percent",
    max_position_weight: float = 0.25,
    target_annual_vol: float = 0.20,
    kelly_fraction: float = 0.25,
    **kwargs: Any,
) -> BasePositionSizer:
    """Factory creating configured position sizer by name."""
    s = name.lower().strip()
    if s in ("volatility_target", "vol_target", "inverse_vol"):
        return VolatilityTargetSizer(
            max_position_weight=max_position_weight,
            target_annual_vol=target_annual_vol,
            **kwargs,
        )
    elif s in ("fractional_kelly", "kelly"):
        return FractionalKellySizer(
            max_position_weight=max_position_weight,
            kelly_fraction=kelly_fraction,
            **kwargs,
        )
    else:
        return FixedPercentSizer(
            max_position_weight=max_position_weight,
            target_annual_vol=target_annual_vol,
            kelly_fraction=kelly_fraction,
        )
