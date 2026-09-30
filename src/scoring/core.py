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
)

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
        w = {**DEFAULT_CORE_WEIGHTS, **(weights or {})}

        # 1. Momentum Score (0-100)
        # Combine 7D return (-15% to +25%), 30D return (-20% to +40%), and acceleration
        r7 = normalize_linear(getattr(features, "return_7d", None), -0.15, 0.25)
        r30 = normalize_linear(getattr(features, "return_30d", None), -0.20, 0.40)
        acc = normalize_linear(getattr(features, "momentum_acceleration", None), -0.10, 0.10)
        momentum_score = clamp((r7 * 0.45) + (r30 * 0.40) + (acc * 0.15))

        # 2. Relative Strength Score (0-100)
        if asset_id == "BTC":
            # For BTC, evaluate momentum vs broader trend and historical dominance
            rs_score = clamp(momentum_score)
        else:
            # For ETH, evaluate excess return vs BTC
            rs_btc = getattr(features, "rs_btc_30d", None)
            rs_score = normalize_linear(rs_btc, -0.15, 0.15)

        # 3. Trend Score (0-100)
        # Price/EMA ratios + ADX trend strength
        ema20_s = normalize_ratio(getattr(features, "ema20_ratio", None), 1.0, 0.08)
        ema50_s = normalize_ratio(getattr(features, "ema50_ratio", None), 1.0, 0.15)
        ema200_s = normalize_ratio(getattr(features, "ema200_ratio", None), 1.0, 0.25)
        adx_s = normalize_linear(getattr(features, "adx_14", None), 10.0, 45.0)
        trend_score = clamp((ema20_s * 0.35) + (ema50_s * 0.35) + (ema200_s * 0.20) + (adx_s * 0.10))

        # 4. Volume Score (0-100)
        # RVOL 20 (0.5 to 2.5) + volume acceleration
        rvol_s = normalize_linear(getattr(features, "volume_to_20d_avg", None), 0.5, 2.5)
        vacc_s = normalize_linear(getattr(features, "volume_acceleration", None), 0.7, 1.5)
        volume_score = clamp((rvol_s * 0.70) + (vacc_s * 0.30))

        # 5. Liquidity Score (0-100)
        # Tight spread (< 15 bps = high score) + turnover ratio
        spread_s = normalize_linear(getattr(features, "spread_est_bps", None), 1.0, 25.0, inverted=True)
        turnover_s = normalize_linear(getattr(features, "turnover_ratio", None), 0.01, 0.15)
        liquidity_score = clamp((spread_s * 0.60) + (turnover_s * 0.40))

        # 6. Fundamentals Score (0-100)
        # TVL growth, fee generation, or neutral baseline if unavailable
        if onchain and getattr(onchain, "tvl_usd", None) is not None:
            tvl_growth = normalize_linear(getattr(onchain, "tvl_change_7d", None), -0.10, 0.10)
            tx_count = normalize_linear(float(getattr(onchain, "tx_count_24h", 0) or 0), 10000.0, 1000000.0)
            fundamentals_score = clamp((tvl_growth * 0.50) + (tx_count * 0.50))
        else:
            fundamentals_score = 65.0  # Stable institutional baseline for core assets

        # 7. Risk Factor (0-100, where 100 is lowest risk / safest)
        realized_vol = normalize_linear(getattr(features, "realized_vol_30d", None), 0.30, 1.20, inverted=True)
        max_dd = normalize_linear(getattr(features, "max_drawdown_90d", None), 5.0, 50.0, inverted=True)
        risk_score = clamp((realized_vol * 0.50) + (max_dd * 0.50))

        # Calculate Quality Score (Fundamental, trend, and liquidity health)
        quality_score = clamp((trend_score * 0.40) + (liquidity_score * 0.30) + (fundamentals_score * 0.30))

        # Component contributions
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
            "risk": FactorContribution(
                name="risk", score=risk_score, weight=w["risk"], contribution=risk_score * w["risk"]
            ),
        }

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
        )
        card.explainability_summary = card.generate_summary()
        return card
