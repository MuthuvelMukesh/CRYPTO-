"""Statistical inference and research integrity metrics: Deflated Sharpe Ratio (DSR) and Multiple Testing Correction.

Implements Bailey & López de Prado (2014):
"The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality"
"""

from __future__ import annotations

import math
from collections.abc import Sequence
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


def bootstrap_confidence_interval(
    data: np.ndarray | Sequence[float],
    statistic_fn: Any = np.mean,
    n_bootstrap: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict[str, float]:
    """Compute empirical non-parametric bootstrap confidence interval for any scalar statistic.

    Args:
        data: Sample 1D array of observations.
        statistic_fn: Callable taking 1D numpy array and returning scalar statistic.
        n_bootstrap: Number of bootstrap resamples (default 1000).
        alpha: Significance level (default 0.05 for 95% CI).
        seed: Random seed for deterministic reproducibility.

    Returns:
        Dict with "estimate", "ci_lower", "ci_upper", "std_err".
    """
    arr = np.asarray(data, dtype=np.float64)
    arr = arr[~np.isnan(arr)]
    n = len(arr)
    if n == 0:
        return {"estimate": 0.0, "ci_lower": 0.0, "ci_upper": 0.0, "std_err": 0.0}

    point_estimate = float(statistic_fn(arr))
    if n < 3:
        return {
            "estimate": round(point_estimate, 4),
            "ci_lower": round(point_estimate, 4),
            "ci_upper": round(point_estimate, 4),
            "std_err": 0.0,
        }

    rng = np.random.default_rng(seed)
    indices = rng.integers(0, n, size=(n_bootstrap, n))
    resamples = arr[indices]

    boot_stats = np.empty(n_bootstrap, dtype=np.float64)
    for i in range(n_bootstrap):
        boot_stats[i] = float(statistic_fn(resamples[i]))

    lower_pct = 100.0 * (alpha / 2.0)
    upper_pct = 100.0 * (1.0 - alpha / 2.0)
    ci_lower = float(np.percentile(boot_stats, lower_pct))
    ci_upper = float(np.percentile(boot_stats, upper_pct))
    std_err = float(np.std(boot_stats, ddof=1))

    return {
        "estimate": round(point_estimate, 4),
        "ci_lower": round(ci_lower, 4),
        "ci_upper": round(ci_upper, 4),
        "std_err": round(std_err, 4),
    }


class StrategyTrialTracker:
    """Thread-safe counter and registry of strategy parameter variants evaluated.

    Tracks total trials N and historical Sharpe ratios to power automated Deflated Sharpe Ratio calculation.
    """

    def __init__(self) -> None:
        import threading
        self._lock = threading.Lock()
        self._trials_count: int = 0
        self._sharpe_ratios: list[float] = []

    def record_trial(self, sharpe_ratio: float, strategy_name: str | None = None) -> int:
        """Record an evaluated strategy trial and its achieved Sharpe ratio."""
        with self._lock:
            self._trials_count += 1
            if not np.isnan(sharpe_ratio) and not np.isinf(sharpe_ratio):
                self._sharpe_ratios.append(float(sharpe_ratio))
            return self._trials_count

    @property
    def total_trials(self) -> int:
        with self._lock:
            return self._trials_count

    def get_distribution_stats(self) -> dict[str, float]:
        """Compute trial count, mean Sharpe, and variance of Sharpes across all trials."""
        with self._lock:
            n = self._trials_count
            if len(self._sharpe_ratios) < 2:
                return {
                    "n_trials": max(1, n),
                    "mean_sharpe": float(self._sharpe_ratios[0]) if self._sharpe_ratios else 0.0,
                    "variance_trials": 0.0,
                }
            arr = np.asarray(self._sharpe_ratios, dtype=np.float64)
            return {
                "n_trials": max(1, n),
                "mean_sharpe": round(float(np.mean(arr)), 4),
                "variance_trials": round(float(np.var(arr, ddof=1)), 6),
            }

    def reset(self) -> None:
        with self._lock:
            self._trials_count = 0
            self._sharpe_ratios.clear()


# Global trial tracker singleton
global_trial_tracker = StrategyTrialTracker()
