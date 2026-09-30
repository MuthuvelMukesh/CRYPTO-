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
)
from src.utils.time import utc_now

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
        w = {**DEFAULT_ALTCOIN_WEIGHTS, **(weights or {})}

        # 1. Momentum Score (0-100)
        r7 = normalize_linear(getattr(features, "return_7d", None), -0.20, 0.35)
        r30 = normalize_linear(getattr(features, "return_30d", None), -0.30, 0.60)
        acc = normalize_linear(getattr(features, "momentum_acceleration", None), -0.15, 0.15)
        momentum_score = clamp((r7 * 0.40) + (r30 * 0.40) + (acc * 0.20))

        # 2. Relative Strength Score (0-100) vs BTC & ETH
        rs_btc = normalize_linear(getattr(features, "rs_btc_30d", None), -0.25, 0.25)
        rs_eth = normalize_linear(getattr(features, "rs_eth_30d", None), -0.25, 0.25)
        rs_score = clamp((rs_btc * 0.60) + (rs_eth * 0.40))

        # 3. Trend Score (0-100)
        ema20_s = normalize_ratio(getattr(features, "ema20_ratio", None), 1.0, 0.10)
        ema50_s = normalize_ratio(getattr(features, "ema50_ratio", None), 1.0, 0.20)
        adx_s = normalize_linear(getattr(features, "adx_14", None), 15.0, 45.0)
        trend_score = clamp((ema20_s * 0.40) + (ema50_s * 0.40) + (adx_s * 0.20))

        # 4. Volume Score (0-100)
        rvol_s = normalize_linear(getattr(features, "volume_to_20d_avg", None), 0.5, 3.0)
        vacc_s = normalize_linear(getattr(features, "volume_acceleration", None), 0.7, 1.8)
        volume_score = clamp((rvol_s * 0.60) + (vacc_s * 0.40))

        # 5. Liquidity Score (0-100)
        spread_s = normalize_linear(getattr(features, "spread_est_bps", None), 2.0, 40.0, inverted=True)
        turnover_s = normalize_linear(getattr(features, "turnover_ratio", None), 0.02, 0.25)
        liquidity_score = clamp((spread_s * 0.50) + (turnover_s * 0.50))

        # 6. Fundamentals Score (0-100)
        if onchain and getattr(onchain, "tvl_usd", None) is not None:
            tvl_growth = normalize_linear(getattr(onchain, "tvl_change_7d", None), -0.15, 0.20)
            revenue_s = normalize_linear(getattr(onchain, "revenue_24h_usd", None), 1000.0, 100000.0)
            fundamentals_score = clamp((tvl_growth * 0.60) + (revenue_s * 0.40))
        else:
            fundamentals_score = 50.0  # Neutral baseline if on-chain metrics unavailable

        # 7. Tokenomics & Structural Risk (0-100)
        fdv_ratio = getattr(tokenomics, "fdv_to_market_cap_ratio", 1.0) if tokenomics else 1.0
        fdv_score = normalize_linear(fdv_ratio, 1.0, 6.0, inverted=True)
        tokenomics_score = clamp(fdv_score)

        # Risk score calculation
        realized_vol = normalize_linear(getattr(features, "realized_vol_30d", None), 0.50, 1.80, inverted=True)
        max_dd = normalize_linear(getattr(features, "max_drawdown_90d", None), 10.0, 65.0, inverted=True)
        risk_score = clamp((realized_vol * 0.50) + (max_dd * 0.50))

        quality_score = clamp((trend_score * 0.35) + (liquidity_score * 0.30) + (fundamentals_score * 0.20) + (tokenomics_score * 0.15))

        # Components
        components = {
            "momentum": FactorContribution(
                name="momentum", score=momentum_score, weight=w["momentum"], contribution=momentum_score * w["momentum"]
            ),
            "relative_strength": FactorContribution(
                name="relative_strength", score=rs_score, weight=w["relative_strength"], contribution=rs_score * w["relative_strength"]
            ),
            "trend": FactorContribution(
                name="trend", score=trend_score, weight=w["trend"], contribution=trend_score * w["trend"]
            ),
            "volume": FactorContribution(
                name="volume", score=volume_score, weight=w["volume"], contribution=volume_score * w["volume"]
            ),
            "liquidity": FactorContribution(
                name="liquidity", score=liquidity_score, weight=w["liquidity"], contribution=liquidity_score * w["liquidity"]
            ),
            "fundamentals": FactorContribution(
                name="fundamentals", score=fundamentals_score, weight=w["fundamentals"], contribution=fundamentals_score * w["fundamentals"]
            ),
            "tokenomics_risk": FactorContribution(
                name="tokenomics_risk", score=tokenomics_score, weight=w["tokenomics_risk"], contribution=tokenomics_score * w["tokenomics_risk"]
            ),
        }

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
        )
        card.explainability_summary = card.generate_summary()
        return card
