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
    redistribute_weights,
    winsorize,
)

SMALLCAP_MODEL_VERSION = "v3.0.0"

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
        w_base = {**DEFAULT_SMALLCAP_WEIGHTS, **(weights or {})}
        missing_inputs: list[str] = []

        # 1. Momentum (0-100) with Winsorization
        r3_val = winsorize(getattr(features, "return_3d", None), -0.50, 1.00)
        r7_val = winsorize(getattr(features, "return_7d", None), -0.70, 1.50)
        acc_val = winsorize(getattr(features, "momentum_acceleration", None), -0.50, 0.50)

        r3 = normalize_linear(r3_val, -0.15, 0.30)
        r7 = normalize_linear(r7_val, -0.25, 0.50)
        acc = normalize_linear(acc_val, -0.20, 0.20)
        momentum_score = clamp((r3 * 0.30) + (r7 * 0.40) + (acc * 0.30))

        # 2. Relative Strength (0-100) vs BTC
        rs_btc_val = winsorize(getattr(features, "rs_btc_30d", None), -0.70, 1.00)
        if rs_btc_val is None:
            missing_inputs.append("relative_strength")
            relative_strength_score = 0.0
        else:
            rs_btc = normalize_linear(rs_btc_val, -0.30, 0.35)
            relative_strength_score = clamp(rs_btc)

        # 3. Trend (0-100)
        ema20_val = winsorize(getattr(features, "ema20_ratio", None), 0.30, 2.50)
        ema20_s = normalize_ratio(ema20_val, 1.0, 0.12)
        trend_score = clamp(ema20_s)

        # 4. Volume Acceleration (0-100)
        rvol_val = winsorize(getattr(features, "volume_to_20d_avg", None), 0.1, 20.0)
        vacc_val = winsorize(getattr(features, "volume_acceleration", None), 0.2, 10.0)
        rvol = normalize_linear(rvol_val, 0.7, 4.0)
        vacc = normalize_linear(vacc_val, 0.8, 2.5)
        volume_score = clamp((rvol * 0.40) + (vacc * 0.60))

        # 5. Liquidity (0-100)
        spread_val = winsorize(getattr(features, "spread_est_bps", None), 0.5, 300.0)
        turnover_val = winsorize(getattr(features, "turnover_ratio", None), 0.001, 2.0)
        spread_s = normalize_linear(spread_val, 5.0, 80.0, inverted=True)
        turnover_s = normalize_linear(turnover_val, 0.05, 0.50)
        liquidity_score = clamp((spread_s * 0.60) + (turnover_s * 0.40))

        # 6. Holder Structure & Tokenomics (0-100) - No silent 50.0 baseline!
        holder_structure_score = 0.0
        has_holder_structure = False
        if holder_metrics and getattr(holder_metrics, "holder_count", 0) > 0:
            growth_val = winsorize(getattr(holder_metrics, "holder_growth_24h_pct", None), -20.0, 50.0)
            conc_val = winsorize(getattr(holder_metrics, "top_10_holders_pct", None), 0.0, 100.0)
            growth_s = normalize_linear(growth_val, 0.0, 5.0)
            conc_s = normalize_linear(conc_val, 20.0, 80.0, inverted=True)
            holder_structure_score = clamp((growth_s * 0.60) + (conc_s * 0.40))
            has_holder_structure = True
        else:
            missing_inputs.append("holder_structure")

        # 7. Risk (0-100, where 100 = lowest risk)
        realized_vol_val = winsorize(getattr(features, "realized_vol_30d", None), 0.1, 5.0)
        max_dd_val = winsorize(getattr(features, "max_drawdown_90d", None), 0.0, 95.0)
        realized_vol = normalize_linear(realized_vol_val, 0.60, 2.50, inverted=True)
        max_dd = normalize_linear(max_dd_val, 15.0, 75.0, inverted=True)
        risk_score = clamp((realized_vol * 0.50) + (max_dd * 0.50))

        # Dynamic weight redistribution
        all_potential_factors = ["momentum", "relative_strength", "trend", "volume_acceleration", "liquidity", "holder_structure", "risk"]
        active_factors = [f for f in all_potential_factors if f not in missing_inputs]
        partial_data = len(missing_inputs) > 0
        w = redistribute_weights(w_base, active_factors)

        # Quality score
        if has_holder_structure:
            quality_score = clamp((liquidity_score * 0.40) + (holder_structure_score * 0.35) + (trend_score * 0.25))
        else:
            quality_score = clamp((liquidity_score * 0.60) + (trend_score * 0.40))

        factor_scores = {
            "momentum": momentum_score,
            "relative_strength": relative_strength_score,
            "trend": trend_score,
            "volume_acceleration": volume_score,
            "liquidity": liquidity_score,
            "holder_structure": holder_structure_score,
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
            partial_data=partial_data,
            missing_inputs=missing_inputs,
            model_version=SMALLCAP_MODEL_VERSION,
        )
        card.explainability_summary = card.generate_summary()
        return card
