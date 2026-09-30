"""Small-cap quantitative scoring model emphasizing liquidity, volume acceleration, and structure."""

from typing import Any

from src.config.constants import AssetClass
from src.scoring.base import (
    BaseScorer,
    FactorContribution,
    PenaltyDeduction,
    ScoreCard,
    clamp,
    normalize_linear,
    normalize_ratio,
)

DEFAULT_SMALLCAP_WEIGHTS = {
    "momentum": 0.20,
    "relative_strength": 0.15,
    "trend": 0.10,
    "volume_acceleration": 0.20,
    "liquidity": 0.15,
    "holder_structure": 0.15,
    "risk": 0.05,
}


class SmallCapScorer(BaseScorer):
    """Specialized factor model for small-cap cryptocurrencies."""

    @property
    def model_type(self) -> str:
        return AssetClass.SMALL_CAP.value

    def calculate_score(
        self,
        asset_id: str,
        features: Any,
        tokenomics: Any | None = None,
        onchain: Any | None = None,
        holder_metrics: Any | None = None,
        weights: dict[str, float] | None = None,
    ) -> ScoreCard:
        w = {**DEFAULT_SMALLCAP_WEIGHTS, **(weights or {})}

        # 1. Momentum (0-100)
        r3 = normalize_linear(getattr(features, "return_3d", None), -0.15, 0.30)
        r7 = normalize_linear(getattr(features, "return_7d", None), -0.25, 0.50)
        acc = normalize_linear(getattr(features, "momentum_acceleration", None), -0.20, 0.20)
        momentum_score = clamp((r3 * 0.30) + (r7 * 0.40) + (acc * 0.30))

        # 2. Relative Strength (0-100) vs BTC
        rs_btc = normalize_linear(getattr(features, "rs_btc_30d", None), -0.30, 0.35)
        relative_strength_score = clamp(rs_btc)

        # 3. Trend (0-100)
        ema20_s = normalize_ratio(getattr(features, "ema20_ratio", None), 1.0, 0.12)
        trend_score = clamp(ema20_s)

        # 4. Volume Acceleration (0-100)
        rvol = normalize_linear(getattr(features, "volume_to_20d_avg", None), 0.7, 4.0)
        vacc = normalize_linear(getattr(features, "volume_acceleration", None), 0.8, 2.5)
        volume_score = clamp((rvol * 0.40) + (vacc * 0.60))

        # 5. Liquidity (0-100)
        spread_s = normalize_linear(getattr(features, "spread_est_bps", None), 5.0, 80.0, inverted=True)
        turnover_s = normalize_linear(getattr(features, "turnover_ratio", None), 0.05, 0.50)
        liquidity_score = clamp((spread_s * 0.60) + (turnover_s * 0.40))

        # 6. Holder Structure & Tokenomics (0-100)
        if holder_metrics and getattr(holder_metrics, "holder_count", 0) > 0:
            growth_s = normalize_linear(getattr(holder_metrics, "holder_growth_24h_pct", None), 0.0, 5.0)
            conc_s = normalize_linear(getattr(holder_metrics, "top_10_holders_pct", None), 20.0, 80.0, inverted=True)
            holder_structure_score = clamp((growth_s * 0.60) + (conc_s * 0.40))
        else:
            holder_structure_score = 50.0

        # 7. Risk (0-100, where 100 = lowest risk)
        realized_vol = normalize_linear(getattr(features, "realized_vol_30d", None), 0.60, 2.50, inverted=True)
        max_dd = normalize_linear(getattr(features, "max_drawdown_90d", None), 15.0, 75.0, inverted=True)
        risk_score = clamp((realized_vol * 0.50) + (max_dd * 0.50))

        quality_score = clamp((liquidity_score * 0.40) + (holder_structure_score * 0.35) + (trend_score * 0.25))

        # Components
        components = {
            "momentum": FactorContribution(
                name="momentum", score=momentum_score, weight=w["momentum"], contribution=momentum_score * w["momentum"]
            ),
            "relative_strength": FactorContribution(
                name="relative_strength", score=relative_strength_score, weight=w["relative_strength"], contribution=relative_strength_score * w["relative_strength"]
            ),
            "trend": FactorContribution(
                name="trend", score=trend_score, weight=w["trend"], contribution=trend_score * w["trend"]
            ),
            "volume_acceleration": FactorContribution(
                name="volume_acceleration", score=volume_score, weight=w["volume_acceleration"], contribution=volume_score * w["volume_acceleration"]
            ),
            "liquidity": FactorContribution(
                name="liquidity", score=liquidity_score, weight=w["liquidity"], contribution=liquidity_score * w["liquidity"]
            ),
            "holder_structure": FactorContribution(
                name="holder_structure", score=holder_structure_score, weight=w["holder_structure"], contribution=holder_structure_score * w["holder_structure"]
            ),
            "risk": FactorContribution(
                name="risk", score=risk_score, weight=w["risk"], contribution=risk_score * w["risk"]
            ),
        }

        # Penalties & Flags
        penalties: list[PenaltyDeduction] = []
        risk_flags: list[str] = []

        spread_bps = getattr(features, "spread_est_bps", 0) or 0
        if spread_bps > 60.0:
            penalties.append(PenaltyDeduction(
                flag="LOW_LIQUIDITY",
                deduction=-15.0,
                reason=f"Wide estimated bid-ask spread ({spread_bps:.0f} bps)",
            ))
            risk_flags.append("LOW_LIQUIDITY")

        if holder_metrics and getattr(holder_metrics, "top_10_holders_pct", 0) > 65.0:
            penalties.append(PenaltyDeduction(
                flag="HIGH_CONCENTRATION",
                deduction=-15.0,
                reason=f"Top 10 wallets hold {getattr(holder_metrics, 'top_10_holders_pct', 0):.1f}% of supply",
            ))
            risk_flags.append("HIGH_CONCENTRATION")

        if getattr(features, "realized_vol_30d", 0) and getattr(features, "realized_vol_30d", 0) > 2.0:
            penalties.append(PenaltyDeduction(
                flag="EXTREME_VOLATILITY",
                deduction=-10.0,
                reason="Annualized 30D volatility exceeds 200%",
            ))
            risk_flags.append("EXTREME_VOLATILITY")

        gross_score = sum(c.contribution for c in components.values())
        total_penalties = sum(p.deduction for p in penalties)
        opportunity_score = clamp(gross_score + total_penalties)

        card = ScoreCard(
            asset_id=asset_id,
            model_type=self.model_type,
            opportunity_score=round(opportunity_score, 1),
            quality_score=round(quality_score, 1),
            risk_score=round(risk_score, 1),
            trend_score=round(trend_score, 1),
            momentum_score=round(momentum_score, 1),
            relative_strength_score=round(relative_strength_score, 1),
            liquidity_score=round(liquidity_score, 1),
            volume_score=round(volume_score, 1),
            components=components,
            penalties=penalties,
            risk_flags=risk_flags,
        )
        card.explainability_summary = card.generate_summary()
        return card
