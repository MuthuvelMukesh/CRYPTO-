"""Dedicated Meme coin quantitative scoring model and risk flag engine."""

from typing import Any

from src.config.constants import AssetClass, RiskFlag
from src.scoring.base import (
    BaseScorer,
    FactorContribution,
    PenaltyDeduction,
    ScoreCard,
    clamp,
    normalize_linear,
    normalize_ratio,
)

DEFAULT_MEME_WEIGHTS = {
    "momentum": 0.25,
    "volume_acceleration": 0.20,
    "liquidity": 0.15,
    "relative_strength": 0.15,
    "holder_structure": 0.10,
    "attention_social": 0.10,
    "risk": 0.05,
}


class MemeScorer(BaseScorer):
    """
    Dedicated Meme Coin quantitative scoring engine.
    Applies rigorous risk penalty deductions for concentration, low liquidity,
    extreme volatility, and abnormal volume.
    """

    @property
    def model_type(self) -> str:
        return AssetClass.MEME.value

    def calculate_score(
        self,
        asset_id: str,
        features: Any,
        tokenomics: Any | None = None,
        onchain: Any | None = None,
        holder_metrics: Any | None = None,
        weights: dict[str, float] | None = None,
    ) -> ScoreCard:
        w = {**DEFAULT_MEME_WEIGHTS, **(weights or {})}

        # 1. Short-Term Momentum (0-100)
        # Meme coins trade on rapid 1D & 3D price velocity and acceleration
        r1 = normalize_linear(getattr(features, "return_1d", None), -0.20, 0.40)
        r3 = normalize_linear(getattr(features, "return_3d", None), -0.30, 0.80)
        acc = normalize_linear(getattr(features, "momentum_acceleration", None), -0.25, 0.35)
        momentum_score = clamp((r1 * 0.35) + (r3 * 0.45) + (acc * 0.20))

        # 2. Volume Acceleration (0-100)
        rvol = normalize_linear(getattr(features, "volume_to_20d_avg", None), 0.8, 5.0)
        vacc = normalize_linear(getattr(features, "volume_acceleration", None), 0.9, 3.0)
        volume_acc_score = clamp((rvol * 0.40) + (vacc * 0.60))

        # 3. Liquidity & Spread (0-100)
        spread_s = normalize_linear(getattr(features, "spread_est_bps", None), 10.0, 150.0, inverted=True)
        turnover_s = normalize_linear(getattr(features, "turnover_ratio", None), 0.10, 1.0)
        liquidity_score = clamp((spread_s * 0.60) + (turnover_s * 0.40))

        # 4. Relative Strength vs BTC (0-100)
        rs_btc = normalize_linear(getattr(features, "rs_btc_30d", None), -0.35, 0.70)
        relative_strength_score = clamp(rs_btc)

        # 5. Holder Structure & Distribution (0-100)
        if holder_metrics and getattr(holder_metrics, "holder_count", 0) > 0:
            growth = normalize_linear(getattr(holder_metrics, "holder_growth_24h_pct", None), 0.0, 15.0)
            conc = normalize_linear(getattr(holder_metrics, "top_10_holders_pct", None), 15.0, 75.0, inverted=True)
            holder_score = clamp((growth * 0.65) + (conc * 0.35))
        else:
            holder_score = 45.0  # Slightly penalize if holder data is unverified

        # 6. Attention / Social (0-100)
        # Social volume & sentiment if available
        attention_score = 50.0

        # 7. Volatility / Risk Base (0-100)
        realized_vol = normalize_linear(getattr(features, "realized_vol_30d", None), 1.0, 3.5, inverted=True)
        risk_score = clamp(realized_vol)

        # Trend score
        ema20_s = normalize_ratio(getattr(features, "ema20_ratio", None), 1.0, 0.15)
        trend_score = clamp(ema20_s)

        quality_score = clamp((liquidity_score * 0.45) + (holder_score * 0.35) + (trend_score * 0.20))

        # Components
        components = {
            "momentum": FactorContribution(
                name="momentum", score=momentum_score, weight=w["momentum"], contribution=momentum_score * w["momentum"]
            ),
            "volume_acceleration": FactorContribution(
                name="volume_acceleration", score=volume_acc_score, weight=w["volume_acceleration"], contribution=volume_acc_score * w["volume_acceleration"]
            ),
            "liquidity": FactorContribution(
                name="liquidity", score=liquidity_score, weight=w["liquidity"], contribution=liquidity_score * w["liquidity"]
            ),
            "relative_strength": FactorContribution(
                name="relative_strength", score=relative_strength_score, weight=w["relative_strength"], contribution=relative_strength_score * w["relative_strength"]
            ),
            "holder_structure": FactorContribution(
                name="holder_structure", score=holder_score, weight=w["holder_structure"], contribution=holder_score * w["holder_structure"]
            ),
            "attention_social": FactorContribution(
                name="attention_social", score=attention_score, weight=w["attention_social"], contribution=attention_score * w["attention_social"]
            ),
            "risk": FactorContribution(
                name="risk", score=risk_score, weight=w["risk"], contribution=risk_score * w["risk"]
            ),
        }

        # Rigorous Meme Risk Flag & Penalty Matrix
        penalties: list[PenaltyDeduction] = []
        risk_flags: list[str] = []

        # 1. High Concentration Flag
        if holder_metrics and getattr(holder_metrics, "top_10_holders_pct", 0) > 60.0:
            penalties.append(PenaltyDeduction(
                flag=RiskFlag.HIGH_CONCENTRATION.value,
                deduction=-25.0,
                reason=f"Top 10 wallets control {getattr(holder_metrics, 'top_10_holders_pct', 0):.1f}% of supply",
            ))
            risk_flags.append(RiskFlag.HIGH_CONCENTRATION.value)

        # 2. Low Liquidity Flag
        spread_bps = getattr(features, "spread_est_bps", 0) or 0
        if spread_bps > 100.0:
            penalties.append(PenaltyDeduction(
                flag=RiskFlag.LOW_LIQUIDITY.value,
                deduction=-20.0,
                reason=f"Severe liquidity friction: estimated spread is {spread_bps:.0f} bps",
            ))
            risk_flags.append(RiskFlag.LOW_LIQUIDITY.value)

        # 3. Extreme Volatility Flag
        vol_30d = getattr(features, "realized_vol_30d", 0) or 0
        if vol_30d > 2.5:
            penalties.append(PenaltyDeduction(
                flag=RiskFlag.EXTREME_VOLATILITY.value,
                deduction=-10.0,
                reason=f"Annualized 30D volatility exceeds 250% ({vol_30d * 100:.0f}%)",
            ))
            risk_flags.append(RiskFlag.EXTREME_VOLATILITY.value)

        # 4. Abnormal Volume Flag (possible wash trading)
        rvol_val = getattr(features, "volume_to_20d_avg", 0) or 0
        if rvol_val > 10.0:
            penalties.append(PenaltyDeduction(
                flag=RiskFlag.ABNORMAL_VOLUME.value,
                deduction=-10.0,
                reason=f"Abnormal volume spike detected ({rvol_val:.1f}x 20-period average)",
            ))
            risk_flags.append(RiskFlag.ABNORMAL_VOLUME.value)

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
            volume_score=round(volume_acc_score, 1),
            components=components,
            penalties=penalties,
            risk_flags=risk_flags,
        )
        card.explainability_summary = card.generate_summary()
        return card
