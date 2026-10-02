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
    redistribute_weights,
    winsorize,
)

MEME_MODEL_VERSION = "v3.0.0"

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
        w_base = {**DEFAULT_MEME_WEIGHTS, **(weights or {})}
        missing_inputs: list[str] = []

        # 1. Short-Term Momentum (0-100) with Winsorization
        r1_val = winsorize(getattr(features, "return_1d", None), -0.60, 1.50)
        r3_val = winsorize(getattr(features, "return_3d", None), -0.80, 3.00)
        acc_val = winsorize(getattr(features, "momentum_acceleration", None), -0.60, 0.60)

        r1 = normalize_linear(r1_val, -0.20, 0.40)
        r3 = normalize_linear(r3_val, -0.30, 0.80)
        acc = normalize_linear(acc_val, -0.25, 0.35)
        momentum_score = clamp((r1 * 0.35) + (r3 * 0.45) + (acc * 0.20))

        # 2. Volume Acceleration (0-100)
        rvol_val = winsorize(getattr(features, "volume_to_20d_avg", None), 0.1, 25.0)
        vacc_val = winsorize(getattr(features, "volume_acceleration", None), 0.2, 12.0)
        rvol = normalize_linear(rvol_val, 0.8, 5.0)
        vacc = normalize_linear(vacc_val, 0.9, 3.0)
        volume_acc_score = clamp((rvol * 0.40) + (vacc * 0.60))

        # 3. Liquidity & Spread (0-100)
        spread_val = winsorize(getattr(features, "spread_est_bps", None), 1.0, 500.0)
        turnover_val = winsorize(getattr(features, "turnover_ratio", None), 0.001, 3.0)
        spread_s = normalize_linear(spread_val, 10.0, 150.0, inverted=True)
        turnover_s = normalize_linear(turnover_val, 0.10, 1.0)
        liquidity_score = clamp((spread_s * 0.60) + (turnover_s * 0.40))

        # 4. Relative Strength vs BTC (0-100)
        rs_btc_val = winsorize(getattr(features, "rs_btc_30d", None), -0.80, 2.00)
        if rs_btc_val is None:
            missing_inputs.append("relative_strength")
            relative_strength_score = 0.0
        else:
            rs_btc = normalize_linear(rs_btc_val, -0.35, 0.70)
            relative_strength_score = clamp(rs_btc)

        # 5. Holder Structure & Distribution (0-100) - No flat 45.0 baseline!
        holder_score = 0.0
        has_holder = False
        if holder_metrics and getattr(holder_metrics, "holder_count", 0) > 0:
            growth_val = winsorize(getattr(holder_metrics, "holder_growth_24h_pct", None), -25.0, 100.0)
            conc_val = winsorize(getattr(holder_metrics, "top_10_holders_pct", None), 0.0, 100.0)
            growth = normalize_linear(growth_val, 0.0, 15.0)
            conc = normalize_linear(conc_val, 15.0, 75.0, inverted=True)
            holder_score = clamp((growth * 0.65) + (conc * 0.35))
            has_holder = True
        else:
            missing_inputs.append("holder_structure")

        # 6. Attention / Social (0-100) - No flat 50.0 baseline!
        social_volume = getattr(features, "social_volume_24h", None)
        attention_score = 0.0
        if social_volume is not None:
            attention_score = normalize_linear(winsorize(float(social_volume), 0.0, 100000.0), 100.0, 10000.0)
        else:
            missing_inputs.append("attention_social")

        # 7. Volatility / Risk Base (0-100)
        realized_vol_val = winsorize(getattr(features, "realized_vol_30d", None), 0.1, 6.0)
        realized_vol = normalize_linear(realized_vol_val, 1.0, 3.5, inverted=True)
        risk_score = clamp(realized_vol)

        # Trend score
        ema20_val = winsorize(getattr(features, "ema20_ratio", None), 0.30, 3.0)
        ema20_s = normalize_ratio(ema20_val, 1.0, 0.15)
        trend_score = clamp(ema20_s)

        # Dynamic weight redistribution
        all_potential_factors = ["momentum", "volume_acceleration", "liquidity", "relative_strength", "holder_structure", "attention_social", "risk"]
        active_factors = [f for f in all_potential_factors if f not in missing_inputs]
        partial_data = len(missing_inputs) > 0
        w = redistribute_weights(w_base, active_factors)

        # Quality score
        if has_holder:
            quality_score = clamp((liquidity_score * 0.45) + (holder_score * 0.35) + (trend_score * 0.20))
        else:
            quality_score = clamp((liquidity_score * 0.65) + (trend_score * 0.35))

        factor_scores = {
            "momentum": momentum_score,
            "volume_acceleration": volume_acc_score,
            "liquidity": liquidity_score,
            "relative_strength": relative_strength_score,
            "holder_structure": holder_score,
            "attention_social": attention_score,
            "risk": risk_score,
        }

        components: dict[str, FactorContribution] = {}
        for f in all_potential_factors:
            score_val = factor_scores[f]
            weight_val = w.get(f, 0.0)
            components[f] = FactorContribution(
                name=f,
                score=score_val,
                weight=round(weight_val, 4),
                contribution=round(score_val * weight_val, 2),
            )

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
            partial_data=partial_data,
            missing_inputs=missing_inputs,
            model_version=MEME_MODEL_VERSION,
        )
        card.explainability_summary = card.generate_summary()
        return card
