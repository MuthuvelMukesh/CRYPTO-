"""Core cryptocurrency multi-factor scoring model (BTC, ETH)."""

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

CORE_MODEL_VERSION = "v3.0.0"

DEFAULT_CORE_WEIGHTS = {
    "momentum": 0.25,
    "relative_strength": 0.20,
    "trend": 0.20,
    "volume": 0.10,
    "liquidity": 0.10,
    "fundamentals": 0.10,
    "risk": 0.05,
}


class CoreScorer(BaseScorer):
    """Institutional-grade quantitative factor model for Core assets (BTC & ETH)."""

    @property
    def model_type(self) -> str:
        return AssetClass.CORE.value

    def calculate_score(
        self,
        asset_id: str,
        features: Any,
        tokenomics: Any | None = None,
        onchain: Any | None = None,
        holder_metrics: Any | None = None,
        weights: dict[str, float] | None = None,
    ) -> ScoreCard:
        w_base = {**DEFAULT_CORE_WEIGHTS, **(weights or {})}
        missing_inputs: list[str] = []

        # 1. Momentum Score (0-100) with Winsorization
        r7_val = winsorize(getattr(features, "return_7d", None), -0.50, 0.50)
        r30_val = winsorize(getattr(features, "return_30d", None), -0.70, 1.00)
        acc_val = winsorize(getattr(features, "momentum_acceleration", None), -0.30, 0.30)

        r7 = normalize_linear(r7_val, -0.15, 0.25)
        r30 = normalize_linear(r30_val, -0.20, 0.40)
        acc = normalize_linear(acc_val, -0.10, 0.10)
        momentum_score = clamp((r7 * 0.45) + (r30 * 0.40) + (acc * 0.15))

        # 2. Relative Strength Score (0-100)
        if asset_id == "BTC":
            rs_score = clamp(momentum_score)
        else:
            rs_val = winsorize(getattr(features, "rs_btc_30d", None), -0.50, 0.50)
            if rs_val is None:
                missing_inputs.append("relative_strength")
                rs_score = 0.0
            else:
                rs_score = normalize_linear(rs_val, -0.15, 0.15)

        # 3. Trend Score (0-100)
        ema20_val = winsorize(getattr(features, "ema20_ratio", None), 0.50, 1.50)
        ema50_val = winsorize(getattr(features, "ema50_ratio", None), 0.40, 1.60)
        ema200_val = winsorize(getattr(features, "ema200_ratio", None), 0.30, 2.00)
        adx_val = winsorize(getattr(features, "adx_14", None), 0.0, 100.0)

        ema20_s = normalize_ratio(ema20_val, 1.0, 0.08)
        ema50_s = normalize_ratio(ema50_val, 1.0, 0.15)
        ema200_s = normalize_ratio(ema200_val, 1.0, 0.25)
        adx_s = normalize_linear(adx_val, 10.0, 45.0)
        trend_score = clamp((ema20_s * 0.35) + (ema50_s * 0.35) + (ema200_s * 0.20) + (adx_s * 0.10))

        # 4. Volume Score (0-100)
        rvol_val = winsorize(getattr(features, "volume_to_20d_avg", None), 0.1, 10.0)
        vacc_val = winsorize(getattr(features, "volume_acceleration", None), 0.2, 5.0)
        rvol_s = normalize_linear(rvol_val, 0.5, 2.5)
        vacc_s = normalize_linear(vacc_val, 0.7, 1.5)
        volume_score = clamp((rvol_s * 0.70) + (vacc_s * 0.30))

        # 5. Liquidity Score (0-100)
        spread_val = winsorize(getattr(features, "spread_est_bps", None), 0.5, 100.0)
        turnover_val = winsorize(getattr(features, "turnover_ratio", None), 0.001, 1.0)
        spread_s = normalize_linear(spread_val, 1.0, 25.0, inverted=True)
        turnover_s = normalize_linear(turnover_val, 0.01, 0.15)
        liquidity_score = clamp((spread_s * 0.60) + (turnover_s * 0.40))

        # 6. Fundamentals Score (0-100) - No flat baselines!
        fundamentals_score = 0.0
        has_fundamentals = False
        if onchain and getattr(onchain, "tvl_usd", None) is not None:
            tvl_growth_val = winsorize(getattr(onchain, "tvl_change_7d", None), -0.50, 0.50)
            tx_count_val = winsorize(float(getattr(onchain, "tx_count_24h", 0) or 0), 0.0, 10000000.0)
            tvl_growth = normalize_linear(tvl_growth_val, -0.10, 0.10)
            tx_count = normalize_linear(tx_count_val, 10000.0, 1000000.0)
            fundamentals_score = clamp((tvl_growth * 0.50) + (tx_count * 0.50))
            has_fundamentals = True
        else:
            missing_inputs.append("fundamentals")

        # 7. Risk Factor (0-100, where 100 is lowest risk / safest)
        rvol_30_val = winsorize(getattr(features, "realized_vol_30d", None), 0.10, 3.0)
        max_dd_val = winsorize(getattr(features, "max_drawdown_90d", None), 0.0, 95.0)
        realized_vol = normalize_linear(rvol_30_val, 0.30, 1.20, inverted=True)
        max_dd = normalize_linear(max_dd_val, 5.0, 50.0, inverted=True)
        risk_score = clamp((realized_vol * 0.50) + (max_dd * 0.50))

        # Determine active factors and redistribute weights dynamically
        all_potential_factors = ["momentum", "relative_strength", "trend", "volume", "liquidity", "fundamentals", "risk"]
        active_factors = [f for f in all_potential_factors if f not in missing_inputs]
        partial_data = len(missing_inputs) > 0
        w = redistribute_weights(w_base, active_factors)

        # Quality Score: computed from present components
        if has_fundamentals:
            quality_score = clamp((trend_score * 0.40) + (liquidity_score * 0.30) + (fundamentals_score * 0.30))
        else:
            quality_score = clamp((trend_score * 0.55) + (liquidity_score * 0.45))

        # Factor contributions with dynamically redistributed weights
        factor_scores = {
            "momentum": momentum_score,
            "relative_strength": rs_score,
            "trend": trend_score,
            "volume": volume_score,
            "liquidity": liquidity_score,
            "fundamentals": fundamentals_score,
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

        # Check risk penalties
        penalties: list[PenaltyDeduction] = []
        risk_flags: list[str] = []

        if getattr(features, "max_drawdown_90d", 0) and getattr(features, "max_drawdown_90d", 0) > 40.0:
            penalties.append(PenaltyDeduction(
                flag="HIGH_DRAWDOWN",
                deduction=-5.0,
                reason="90-day drawdown exceeds 40%",
            ))
            risk_flags.append("HIGH_DRAWDOWN")

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
            relative_strength_score=round(rs_score, 1),
            liquidity_score=round(liquidity_score, 1),
            volume_score=round(volume_score, 1),
            components=components,
            penalties=penalties,
            risk_flags=risk_flags,
            partial_data=partial_data,
            missing_inputs=missing_inputs,
            model_version=CORE_MODEL_VERSION,
        )
        card.explainability_summary = card.generate_summary()
        return card
