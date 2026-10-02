"""Forward-return attribution, Information Coefficient (IC), and score decile analytics.

Provides institutional factor attribution verifying if opportunity scores produce
statistically significant forward returns at 1d, 7d, and 30d horizons.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from src.config.constants import DataMode
from src.research.statistics import bootstrap_confidence_interval


@dataclass
class DecileBucket:
    """Performance statistics for a single score decile bucket."""

    decile: int  # 1 (lowest score) to 10 (highest score)
    score_min: float
    score_max: float
    sample_size: int
    mean_forward_return_pct: float
    median_forward_return_pct: float
    std_forward_return_pct: float
    annualized_return_pct: float
    positive_return_ratio: float


class AttributionReport(BaseModel):
    """Complete institutional forward-return factor attribution report."""

    horizon: str = Field(..., description="Forward return horizon ('1d', '7d', '30d')")
    sample_size: int = Field(..., description="Number of snapshot observation pairs analyzed")
    data_mode: str = Field(default=DataMode.HISTORICAL.value, description="Data provenance mode")
    pearson_ic: float = Field(..., description="Linear correlation between score and forward return")
    pearson_p_value: float = Field(..., description="P-value for H0: Pearson IC == 0")
    pearson_ci_lower: float = Field(..., description="95% Bootstrap CI lower bound for Pearson IC")
    pearson_ci_upper: float = Field(..., description="95% Bootstrap CI upper bound for Pearson IC")
    spearman_rank_ic: float = Field(..., description="Rank correlation between score rank and return rank")
    spearman_p_value: float = Field(..., description="P-value for H0: Spearman Rank IC == 0")
    spearman_ci_lower: float = Field(..., description="95% Bootstrap CI lower bound for Spearman IC")
    spearman_ci_upper: float = Field(..., description="95% Bootstrap CI upper bound for Spearman IC")
    hit_rate_pct: float = Field(..., description="Percentage of scores > 50 yielding positive forward return")
    hit_rate_ci_lower: float = Field(..., description="95% Bootstrap CI lower bound for hit rate")
    hit_rate_ci_upper: float = Field(..., description="95% Bootstrap CI upper bound for hit rate")
    deciles: list[dict[str, Any]] = Field(default_factory=list, description="Performance across deciles 1-10")
    monotonicity_spread_pct: float = Field(
        default=0.0, description="Decile 10 mean return minus Decile 1 mean return"
    )
    small_sample_warning: bool = Field(
        default=False, description="True if sample size N < 30 indicates high estimator variance"
    )
    small_sample_message: str | None = Field(
        default=None, description="Plain-language warning if sample size is insufficient"
    )
    plain_language_summary: str = Field(
        default="", description="Plain-language interpretation of statistical factor efficacy"
    )


def compute_pearson_correlation(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Compute Pearson correlation, t-statistic, and two-tailed p-value."""
    n = len(x)
    if n < 3:
        return 0.0, 0.0, 1.0

    var_x = float(np.var(x, ddof=1))
    var_y = float(np.var(y, ddof=1))

    if var_x < 1e-12 or var_y < 1e-12:
        return 0.0, 0.0, 1.0

    cov_xy = float(np.cov(x, y)[0, 1])
    r = cov_xy / math.sqrt(var_x * var_y)
    r = max(-1.0, min(1.0, r))

    # Student's t distribution approximation for correlation
    df = n - 2
    if abs(r) >= 1.0:
        t_stat = 999.0 * math.copysign(1.0, r)
        p_val = 0.0
    else:
        denom = math.sqrt((1.0 - r**2) / df)
        t_stat = r / denom if denom > 1e-12 else 0.0
        # Standard normal approximation for p-value if df >= 20, or erf
        z = abs(t_stat)
        p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2.0))))
        p_val = max(0.0, min(1.0, p_val))

    return float(r), float(t_stat), float(p_val)


def compute_spearman_correlation(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Compute Spearman rank correlation coefficient and p-value."""
    n = len(x)
    if n < 3:
        return 0.0, 0.0, 1.0

    rank_x = np.argsort(np.argsort(x)).astype(np.float64)
    rank_y = np.argsort(np.argsort(y)).astype(np.float64)
    return compute_pearson_correlation(rank_x, rank_y)


def calculate_deciles(
    scores: np.ndarray,
    returns: np.ndarray,
    n_deciles: int = 10,
    horizon_days: float = 1.0,
) -> tuple[list[DecileBucket], float]:
    """Group observations into 10 score-ranked deciles and calculate performance metrics."""
    n = len(scores)
    if n == 0:
        return [], 0.0

    # Sort indices by score ascending
    sort_idx = np.argsort(scores)
    sorted_scores = scores[sort_idx]
    sorted_returns = returns[sort_idx]

    # Split into n_deciles chunks
    buckets: list[DecileBucket] = []
    chunk_size = max(1, n / n_deciles)

    periods_per_year = max(1.0, 365.25 / horizon_days)

    for d in range(n_deciles):
        start_idx = int(round(d * chunk_size))
        end_idx = int(round((d + 1) * chunk_size)) if d < n_deciles - 1 else n
        end_idx = max(start_idx + 1, min(n, end_idx))

        bucket_scores = sorted_scores[start_idx:end_idx]
        bucket_returns = sorted_returns[start_idx:end_idx]

        b_len = len(bucket_returns)
        if b_len == 0:
            continue

        mean_r = float(np.mean(bucket_returns))
        median_r = float(np.median(bucket_returns))
        std_r = float(np.std(bucket_returns, ddof=1)) if b_len > 1 else 0.0
        pos_ratio = float(np.sum(bucket_returns > 0) / b_len)

        # Annualized return approximation
        ann_return = mean_r * periods_per_year * 100.0

        buckets.append(
            DecileBucket(
                decile=d + 1,
                score_min=round(float(np.min(bucket_scores)), 1),
                score_max=round(float(np.max(bucket_scores)), 1),
                sample_size=b_len,
                mean_forward_return_pct=round(mean_r * 100.0, 2),
                median_forward_return_pct=round(median_r * 100.0, 2),
                std_forward_return_pct=round(std_r * 100.0, 2),
                annualized_return_pct=round(ann_return, 2),
                positive_return_ratio=round(pos_ratio, 4),
            )
        )

    # Monotonicity spread: Decile 10 mean return - Decile 1 mean return
    spread = 0.0
    if len(buckets) >= 2:
        spread = round(buckets[-1].mean_forward_return_pct - buckets[0].mean_forward_return_pct, 2)

    return buckets, spread


def generate_attribution_report(
    scores: Sequence[float],
    forward_returns: Sequence[float],
    horizon: str = "1d",
    data_mode: DataMode = DataMode.HISTORICAL,
    min_samples: int = 30,
) -> AttributionReport:
    """Generate comprehensive research factor attribution report.

    Args:
        scores: Sequence of multi-factor opportunity scores (0-100).
        forward_returns: Sequence of fractional forward returns over the horizon (e.g. +0.05 for +5%).
        horizon: Horizon identifier ("1d", "7d", "30d").
        data_mode: Provenance data mode.
        min_samples: Sample threshold below which small sample warning is triggered.

    Returns:
        AttributionReport with IC, CIs, hit rate, deciles, and plain-language summary.
    """
    scores_arr = np.asarray(scores, dtype=np.float64)
    returns_arr = np.asarray(forward_returns, dtype=np.float64)

    # Filter out NaNs
    valid_mask = (~np.isnan(scores_arr)) & (~np.isnan(returns_arr))
    scores_clean = scores_arr[valid_mask]
    returns_clean = returns_arr[valid_mask]

    n = len(scores_clean)

    horizon_days_map = {"1d": 1.0, "24h": 1.0, "7d": 7.0, "30d": 30.0}
    horizon_days = horizon_days_map.get(horizon.lower(), 1.0)

    if n < 3:
        return AttributionReport(
            horizon=horizon,
            sample_size=n,
            data_mode=data_mode.value,
            pearson_ic=0.0,
            pearson_p_value=1.0,
            pearson_ci_lower=0.0,
            pearson_ci_upper=0.0,
            spearman_rank_ic=0.0,
            spearman_p_value=1.0,
            spearman_ci_lower=0.0,
            spearman_ci_upper=0.0,
            hit_rate_pct=0.0,
            hit_rate_ci_lower=0.0,
            hit_rate_ci_upper=0.0,
            deciles=[],
            monotonicity_spread_pct=0.0,
            small_sample_warning=True,
            small_sample_message=f"Insufficient sample size (N={n}). Minimum 3 observations required.",
            plain_language_summary="Insufficient historical snapshot data to calculate forward attribution.",
        )

    # 1. Pearson IC & Spearman IC
    pearson_r, _, pearson_p = compute_pearson_correlation(scores_clean, returns_clean)
    spearman_r, _, spearman_p = compute_spearman_correlation(scores_clean, returns_clean)

    # 2. Bootstrap CIs for Pearson & Spearman IC
    # Fast bivariate bootstrap
    rng = np.random.default_rng(42)
    n_boot = min(1000, max(200, n * 5))
    boot_idx = rng.integers(0, n, size=(n_boot, n))

    pearson_boots = np.empty(n_boot, dtype=np.float64)
    spearman_boots = np.empty(n_boot, dtype=np.float64)
    for b in range(n_boot):
        sample_sc = scores_clean[boot_idx[b]]
        sample_ret = returns_clean[boot_idx[b]]
        pr, _, _ = compute_pearson_correlation(sample_sc, sample_ret)
        sr, _, _ = compute_spearman_correlation(sample_sc, sample_ret)
        pearson_boots[b] = pr
        spearman_boots[b] = sr

    pearson_ci_lower = float(np.percentile(pearson_boots, 2.5))
    pearson_ci_upper = float(np.percentile(pearson_boots, 97.5))
    spearman_ci_lower = float(np.percentile(spearman_boots, 2.5))
    spearman_ci_upper = float(np.percentile(spearman_boots, 97.5))

    # 3. Hit Rate: % of assets where score >= 50.0 produced positive return
    score_above_50 = scores_clean >= 50.0
    if np.any(score_above_50):
        hits = (returns_clean[score_above_50] > 0).astype(np.float64)
        hit_rate = float(np.mean(hits) * 100.0)
        boot_hit = bootstrap_confidence_interval(hits, statistic_fn=lambda a: float(np.mean(a) * 100.0), seed=42)
        hit_ci_lower = boot_hit["ci_lower"]
        hit_ci_upper = boot_hit["ci_upper"]
    else:
        hit_rate = 50.0
        hit_ci_lower = 50.0
        hit_ci_upper = 50.0

    # 4. Deciles & Monotonicity
    decile_buckets, monotonicity_spread = calculate_deciles(
        scores_clean, returns_clean, n_deciles=10, horizon_days=horizon_days
    )
    deciles_json = [
        {
            "decile": b.decile,
            "score_min": b.score_min,
            "score_max": b.score_max,
            "sample_size": b.sample_size,
            "mean_forward_return_pct": b.mean_forward_return_pct,
            "median_forward_return_pct": b.median_forward_return_pct,
            "std_forward_return_pct": b.std_forward_return_pct,
            "annualized_return_pct": b.annualized_return_pct,
            "positive_return_ratio": b.positive_return_ratio,
        }
        for b in decile_buckets
    ]

    # 5. Small Sample Warning
    small_sample = n < min_samples
    small_sample_msg = (
        f"Warning: sample size N={n} is below recommended minimum ({min_samples}). "
        "Confidence intervals are wide and results should be considered preliminary."
        if small_sample
        else None
    )

    # 6. Plain-language explainer summary
    ic_strength = "strong" if abs(spearman_r) >= 0.15 else ("moderate" if abs(spearman_r) >= 0.05 else "weak")
    direction = "positive (higher scores predict higher returns)" if spearman_r > 0 else "negative (inverse correlation)"
    sig_text = "statistically significant (p < 0.05)" if spearman_p < 0.05 else "not statistically significant (p >= 0.05)"

    summary = (
        f"Over {n} evaluated {horizon} observations ({data_mode.value} data), the multi-factor scoring model exhibits "
        f"{ic_strength} {direction} rank correlation with a Spearman IC of {spearman_r:+.3f} [{spearman_ci_lower:+.3f}, {spearman_ci_upper:+.3f}], "
        f"which is {sig_text}. "
        f"The hit rate for scores >= 50 is {hit_rate:.1f}%. "
        f"Top-decile assets (Decile 10) outperformed bottom-decile assets (Decile 1) by {monotonicity_spread:+.2f}% over {horizon}."
    )

    return AttributionReport(
        horizon=horizon,
        sample_size=n,
        data_mode=data_mode.value,
        pearson_ic=round(pearson_r, 4),
        pearson_p_value=round(pearson_p, 4),
        pearson_ci_lower=round(pearson_ci_lower, 4),
        pearson_ci_upper=round(pearson_ci_upper, 4),
        spearman_rank_ic=round(spearman_r, 4),
        spearman_p_value=round(spearman_p, 4),
        spearman_ci_lower=round(spearman_ci_lower, 4),
        spearman_ci_upper=round(spearman_ci_upper, 4),
        hit_rate_pct=round(hit_rate, 2),
        hit_rate_ci_lower=round(hit_ci_lower, 2),
        hit_rate_ci_upper=round(hit_ci_upper, 2),
        deciles=deciles_json,
        monotonicity_spread_pct=monotonicity_spread,
        small_sample_warning=small_sample,
        small_sample_message=small_sample_msg,
        plain_language_summary=summary,
    )


def generate_synthetic_attribution_dataset(
    n_samples: int = 500,
    target_ic: float = 0.20,
    horizon: str = "1d",
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a synthetic dataset with known ground-truth correlation (Information Coefficient).

    Used for verification and testing under DataMode.SYNTHETIC_TEST.

    Model:
        X ~ Uniform(20, 90) -> mapped to Opportunity Score
        Z ~ Normal(0, 1) standard normal score
        noise ~ Normal(0, 1)
        Y = target_ic * Z + sqrt(1 - target_ic^2) * noise
        forward_returns = Y * return_std (e.g. 3% daily return vol)
    """
    rng = np.random.default_rng(seed)
    # Generate scores with uniform distribution bounded [20, 95]
    scores = rng.uniform(20.0, 95.0, size=n_samples)

    # Standardize score to Z
    z_score = (scores - np.mean(scores)) / np.std(scores)

    # Correlated return signal
    noise = rng.normal(0.0, 1.0, size=n_samples)
    rho = max(-0.95, min(0.95, target_ic))
    y = (rho * z_score) + (math.sqrt(1.0 - rho**2) * noise)

    # Scale to reasonable crypto return magnitude (e.g. daily std dev 4%)
    daily_vol = 0.04
    forward_returns = y * daily_vol

    return scores, forward_returns
