"""Altcoin multi-factor scoring model for Mid and Large-Cap altcoins."""

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
from src.utils.time import utc_now

ALTCOIN_MODEL_VERSION = "v3.0.0"

DEFAULT_ALTCOIN_WEIGHTS = {
    "momentum": 0.25,
    "relative_strength": 0.20,
    "trend": 0.15,
    "volume": 0.15,
    "liquidity": 0.10,
    "fundamentals": 0.10,
    "tokenomics_risk": 0.05,
}


class AltcoinScorer(BaseScorer):
    """Quantitative scoring model tailored for Mid and Large-Cap altcoins."""

    @property
    def model_type(self) -> str:
        return AssetClass.ALTCOIN.value

    def calculate_score(
        self,
        asset_id: str,
        features: Any,
        tokenomics: Any | None = None,
        onchain: Any | None = None,
        holder_metrics: Any | None = None,
        weights: dict[str, float] | None = None,
    ) -> ScoreCard:
        w_base = {**DEFAULT_ALTCOIN_WEIGHTS, **(weights or {})}
        missing_inputs: list[str] = []

        # 1. Momentum Score (0-100) with Winsorization
        r7_val = winsorize(getattr(features, "return_7d", None), -0.60, 1.00)
        r30_val = winsorize(getattr(features, "return_30d", None), -0.80, 2.00)
        acc_val = winsorize(getattr(features, "momentum_acceleration", None), -0.50, 0.50)

        r7 = normalize_linear(r7_val, -0.20, 0.35)
        r30 = normalize_linear(r30_val, -0.30, 0.60)
        acc = normalize_linear(acc_val, -0.15, 0.15)
        momentum_score = clamp((r7 * 0.40) + (r30 * 0.40) + (acc * 0.20))

        # 2. Relative Strength Score (0-100) vs BTC & ETH
        rs_btc_val = winsorize(getattr(features, "rs_btc_30d", None), -0.60, 1.00)
        rs_eth_val = winsorize(getattr(features, "rs_eth_30d", None), -0.60, 1.00)

        if rs_btc_val is None and rs_eth_val is None:
            missing_inputs.append("relative_strength")
            rs_score = 0.0
        else:
            rs_btc = normalize_linear(rs_btc_val, -0.25, 0.25)
            rs_eth = normalize_linear(rs_eth_val, -0.25, 0.25)
            rs_score = clamp((rs_btc * 0.60) + (rs_eth * 0.40))

        # 3. Trend Score (0-100)
        ema20_val = winsorize(getattr(features, "ema20_ratio", None), 0.40, 2.00)
        ema50_val = winsorize(getattr(features, "ema50_ratio", None), 0.40, 2.00)
        adx_val = winsorize(getattr(features, "adx_14", None), 0.0, 100.0)

        ema20_s = normalize_ratio(ema20_val, 1.0, 0.10)
        ema50_s = normalize_ratio(ema50_val, 1.0, 0.20)
        adx_s = normalize_linear(adx_val, 15.0, 45.0)
        trend_score = clamp((ema20_s * 0.40) + (ema50_s * 0.40) + (adx_s * 0.20))

        # 4. Volume Score (0-100)
        rvol_val = winsorize(getattr(features, "volume_to_20d_avg", None), 0.1, 15.0)
        vacc_val = winsorize(getattr(features, "volume_acceleration", None), 0.2, 8.0)
        rvol_s = normalize_linear(rvol_val, 0.5, 3.0)
        vacc_s = normalize_linear(vacc_val, 0.7, 1.8)
        volume_score = clamp((rvol_s * 0.60) + (vacc_s * 0.40))

        # 5. Liquidity Score (0-100)
        spread_val = winsorize(getattr(features, "spread_est_bps", None), 0.5, 200.0)
        turnover_val = winsorize(getattr(features, "turnover_ratio", None), 0.001, 1.5)
        spread_s = normalize_linear(spread_val, 2.0, 40.0, inverted=True)
        turnover_s = normalize_linear(turnover_val, 0.02, 0.25)
        liquidity_score = clamp((spread_s * 0.50) + (turnover_s * 0.50))

        # 6. Fundamentals Score (0-100) - No silent 50.0 baseline!
        fundamentals_score = 0.0
        has_fundamentals = False
        if onchain and getattr(onchain, "tvl_usd", None) is not None:
            tvl_growth_val = winsorize(getattr(onchain, "tvl_change_7d", None), -0.50, 0.50)
            revenue_val = winsorize(getattr(onchain, "revenue_24h_usd", None), 0.0, 5000000.0)
            tvl_growth = normalize_linear(tvl_growth_val, -0.15, 0.20)
            revenue_s = normalize_linear(revenue_val, 1000.0, 100000.0)
            fundamentals_score = clamp((tvl_growth * 0.60) + (revenue_s * 0.40))
            has_fundamentals = True
        else:
            missing_inputs.append("fundamentals")

        # 7. Tokenomics & Structural Risk (0-100) - No silent baseline!
        tokenomics_score = 0.0
        has_tokenomics = False
        if tokenomics and getattr(tokenomics, "fdv_to_market_cap_ratio", None) is not None:
            fdv_ratio_val = winsorize(getattr(tokenomics, "fdv_to_market_cap_ratio", None), 0.5, 50.0)
            fdv_score = normalize_linear(fdv_ratio_val, 1.0, 6.0, inverted=True)
            tokenomics_score = clamp(fdv_score)
            has_tokenomics = True
        else:
            missing_inputs.append("tokenomics_risk")

        # Risk score calculation
        realized_vol_val = winsorize(getattr(features, "realized_vol_30d", None), 0.1, 4.0)
        max_dd_val = winsorize(getattr(features, "max_drawdown_90d", None), 0.0, 95.0)
        realized_vol = normalize_linear(realized_vol_val, 0.50, 1.80, inverted=True)
        max_dd = normalize_linear(max_dd_val, 10.0, 65.0, inverted=True)
        risk_score = clamp((realized_vol * 0.50) + (max_dd * 0.50))

        # Dynamic weight redistribution
        all_potential_factors = ["momentum", "relative_strength", "trend", "volume", "liquidity", "fundamentals", "tokenomics_risk"]
        active_factors = [f for f in all_potential_factors if f not in missing_inputs]
        partial_data = len(missing_inputs) > 0
        w = redistribute_weights(w_base, active_factors)

        # Quality score computed only from active quality components
        quality_terms: list[tuple[float, float]] = [(trend_score, 0.40), (liquidity_score, 0.35)]
        if has_fundamentals:
            quality_terms.append((fundamentals_score, 0.15))
        if has_tokenomics:
            quality_terms.append((tokenomics_score, 0.10))
        total_q_w = sum(wt for _, wt in quality_terms)
        quality_score = clamp(sum(sc * (wt / total_q_w) for sc, wt in quality_terms))

        factor_scores = {
            "momentum": momentum_score,
            "relative_strength": rs_score,
            "trend": trend_score,
            "volume": volume_score,
            "liquidity": liquidity_score,
            "fundamentals": fundamentals_score,
            "tokenomics_risk": tokenomics_score,
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

        # Penalties & Risk Flags
        penalties: list[PenaltyDeduction] = []
        risk_flags: list[str] = []

        if tokenomics:
            if getattr(tokenomics, "fdv_to_market_cap_ratio", 0) and getattr(tokenomics, "fdv_to_market_cap_ratio", 0) > 4.0:
                penalties.append(PenaltyDeduction(
                    flag="SUPPLY_RISK",
                    deduction=-8.0,
                    reason=f"High FDV / Market Cap overhang ({getattr(tokenomics, 'fdv_to_market_cap_ratio', 0):.1f}x)",
                ))
                risk_flags.append("SUPPLY_RISK")

            # Check unlock within 48h
            unlock_date = getattr(tokenomics, "next_unlock_date", None)
            if unlock_date:
                hours_until = (unlock_date - utc_now()).total_seconds() / 3600.0
                if 0 < hours_until <= 72.0:
                    penalties.append(PenaltyDeduction(
                        flag="UPCOMING_UNLOCK_48H",
                        deduction=-10.0,
                        reason=f"Token unlock occurring in {int(hours_until)} hours",
                    ))
                    risk_flags.append("UPCOMING_UNLOCK_48H")

        if getattr(features, "max_drawdown_90d", 0) and getattr(features, "max_drawdown_90d", 0) > 50.0:
            penalties.append(PenaltyDeduction(
                flag="HIGH_DRAWDOWN",
                deduction=-5.0,
                reason="90-day drawdown exceeds 50%",
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
            model_version=ALTCOIN_MODEL_VERSION,
        )
        card.explainability_summary = card.generate_summary()
        return card
