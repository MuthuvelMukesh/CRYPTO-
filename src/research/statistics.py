"""Statistical inference and research integrity metrics: Deflated Sharpe Ratio (DSR) and Multiple Testing Correction.

Implements Bailey & López de Prado (2014):
"The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality"
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def compute_probabilistic_sharpe_ratio(
    sharpe_ratio: float,
    benchmark_sharpe: float = 0.0,
    n_observations: int = 252,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Compute the Probabilistic Sharpe Ratio (PSR).

    PSR measures the probability that the estimated Sharpe Ratio is greater
    than a benchmark Sharpe Ratio, accounting for skewness, kurtosis, and sample length.
    """
    if n_observations < 2:
        return 0.50

    # Variance of Sharpe ratio estimator (Mertens 1996 / Lo 2002)
    # sigma_sr^2 = (1 - skew * sr + (kurt - 1)/4 * sr^2) / (T - 1)
    variance_term = 1.0 - (skewness * sharpe_ratio) + (((kurtosis - 1.0) / 4.0) * (sharpe_ratio**2))
    variance_term = max(1e-8, variance_term)
    std_err = math.sqrt(variance_term / (n_observations - 1))

    z = (sharpe_ratio - benchmark_sharpe) / std_err
    psr = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return float(np.clip(psr, 0.0, 1.0))


def compute_expected_max_sharpe(
    n_trials: int,
    variance_trials: float,
    euler_mascheroni: float = 0.5772156649,
) -> float:
    """Compute expected maximum Sharpe ratio among N trials under the null hypothesis (SR=0).

    Uses the extreme value theory approximation:
    E[max_N] = sqrt(V) * ((1 - gamma) * Z^{-1}(1 - 1/N) + gamma * Z^{-1}(1 - 1/(N * e)))
    or the standard limit: sqrt(V) * (sqrt(2 * ln(N)) + gamma / sqrt(2 * ln(N))).
    """
    if n_trials <= 1 or variance_trials <= 0.0:
        return 0.0

    std_trials = math.sqrt(variance_trials)
    ln_n = math.log(n_trials)
    sqrt_2_ln_n = math.sqrt(2.0 * ln_n)

    # Extreme value theory approximation
    expected_z = sqrt_2_ln_n + (euler_mascheroni / sqrt_2_ln_n)
    return float(std_trials * expected_z)


def compute_deflated_sharpe_ratio(
    sharpe_ratio: float,
    n_observations: int,
    n_trials: int = 1,
    variance_trials: float = 0.0,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    returns: np.ndarray | list[float] | None = None,
) -> dict[str, Any]:
    """Compute the Deflated Sharpe Ratio (DSR) correcting for multiple testing and non-normality.

    Args:
        sharpe_ratio: Estimated Sharpe Ratio of the selected strategy (per observation).
        n_observations: Number of historical return observations T.
        n_trials: Number of independent/dependent strategy parameter trials tested N.
        variance_trials: Variance of Sharpe ratios across all tested trials V.
        skewness: Return distribution skewness (gamma_3).
        kurtosis: Return distribution kurtosis (gamma_4, normal = 3.0).
        returns: Optional array of return observations to calculate empirical skew and kurtosis.

    Returns:
        Dict with DSR, PSR, expected_max_sharpe, z_stat, standard_error, n_trials, variance_trials.
    """
    # If returns array provided, derive empirical statistics
    if returns is not None and len(returns) >= 5:
        ret_arr = np.asarray(returns, dtype=np.float64)
        n_observations = len(ret_arr)
        mean_r = np.mean(ret_arr)
        std_r = np.std(ret_arr, ddof=1)
        if std_r > 1e-9:
            sharpe_ratio = float(mean_r / std_r)
            # Sample skewness
            z_ret = (ret_arr - mean_r) / std_r
            skewness = float(np.mean(z_ret**3))
            kurtosis = float(np.mean(z_ret**4))

    # 1. Expected Maximum Sharpe Ratio under multiple testing
    e_max_sr = compute_expected_max_sharpe(n_trials=n_trials, variance_trials=variance_trials)

    # 2. Standard error of Sharpe ratio
    if n_observations < 2:
        return {
            "deflated_sharpe_ratio": 0.50,
            "probabilistic_sharpe_ratio": 0.50,
            "expected_max_sharpe": 0.0,
            "z_stat": 0.0,
            "standard_error": 0.0,
            "n_trials": n_trials,
            "variance_trials": variance_trials,
        }

    variance_term = 1.0 - (skewness * sharpe_ratio) + (((kurtosis - 1.0) / 4.0) * (sharpe_ratio**2))
    variance_term = max(1e-8, variance_term)
    std_err = math.sqrt(variance_term / (n_observations - 1))

    # 3. Z-score relative to expected maximum
    z_stat = (sharpe_ratio - e_max_sr) / std_err if std_err > 1e-9 else 0.0

    # 4. Deflated Sharpe Ratio = Phi(z_stat)
    dsr = 0.5 * (1.0 + math.erf(z_stat / math.sqrt(2.0)))
    dsr = float(np.clip(dsr, 0.0, 1.0))

    # 5. Standard PSR for comparison
    psr = compute_probabilistic_sharpe_ratio(
        sharpe_ratio=sharpe_ratio,
        benchmark_sharpe=0.0,
        n_observations=n_observations,
        skewness=skewness,
        kurtosis=kurtosis,
    )

    return {
        "deflated_sharpe_ratio": round(dsr, 4),
        "probabilistic_sharpe_ratio": round(psr, 4),
        "expected_max_sharpe": round(e_max_sr, 4),
        "z_stat": round(z_stat, 4),
        "standard_error": round(std_err, 4),
        "n_trials": n_trials,
        "variance_trials": round(variance_trials, 6),
        "skewness": round(skewness, 4),
        "kurtosis": round(kurtosis, 4),
    }
