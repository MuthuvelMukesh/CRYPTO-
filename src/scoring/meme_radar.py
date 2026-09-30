"""Meme Coin Radar and DEX intelligence engine with risk penalty audit."""

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.ingestion.providers.dexscreener_provider import DexPairMetrics, DexScreenerProvider
from src.utils.logging import get_logger

logger = get_logger("meme_radar")


class MemeAuditRecord(BaseModel):
    """Comprehensive quantitative analysis and risk card for a meme token."""

    model_config = ConfigDict(protected_namespaces=())

    symbol: str
    name: str
    chain_id: str
    dex_id: str
    pair_address: str
    price_usd: float
    liquidity_usd: float
    volume_24h_usd: float
    volume_acceleration_1h: float
    volume_acceleration_5m: float
    buy_pressure_ratio: float  # buys / (buys + sells)
    pair_age_hours: float
    top_10_holders_pct: float
    holder_count: int

    # Quantitative Component Scores (0-100)
    liquidity_score: float
    volume_momentum_score: float
    buy_pressure_score: float
    holder_distribution_score: float

    # Composite Score & Penalties
    gross_score: float
    total_penalties: float
    opportunity_score: float
    risk_level: str  # LOW, MODERATE, HIGH, CRITICAL
    risk_flags: list[str] = Field(default_factory=list)
    penalties_breakdown: list[dict[str, Any]] = Field(default_factory=list)


class MemeRadarEngine:
    """Quantitative scanner specialized in DEX liquidity dynamics, volume bursts, and meme risk flags."""

    def __init__(self, provider: DexScreenerProvider | None = None) -> None:
        self.provider = provider or DexScreenerProvider()

    def analyze_pair(
        self,
        pair: DexPairMetrics,
        top_10_holders_pct: float = 45.0,
        holder_count: int = 15000,
    ) -> MemeAuditRecord:
        """Perform quantitative scoring and risk audit on a DEX pair."""
        # 1. Liquidity Health Score (0-100)
        # Logarithmic scale: $10k -> 25, $100k -> 55, $1M -> 80, $10M+ -> 98
        raw_liq = max(100.0, pair.liquidity_usd)
        liq_score = min(100.0, max(0.0, (math.log10(raw_liq) - 3.0) * 25.0))

        # 2. Volume Momentum & Acceleration (0-100)
        # 1h volume annualized vs 24h volume
        expected_1h_vol = pair.volume_24h_usd / 24.0
        accel_1h = (pair.volume_1h_usd / expected_1h_vol) if expected_1h_vol > 0 else 1.0
        expected_5m_vol = pair.volume_24h_usd / 288.0
        accel_5m = (pair.volume_5m_usd / expected_5m_vol) if expected_5m_vol > 0 else 1.0

        vol_burst = (accel_1h * 0.6) + (accel_5m * 0.4)
        vol_score = min(100.0, max(10.0, 50.0 + ((vol_burst - 1.0) * 25.0)))

        # 3. Buy Pressure Score (0-100)
        buy_score = min(100.0, max(0.0, pair.buy_pressure_ratio * 100.0))

        # 4. Holder Distribution Score (0-100)
        # Top 10 holders under 40% is excellent (100 pts), above 80% is 0 pts
        holder_score = min(100.0, max(0.0, (80.0 - top_10_holders_pct) * 2.5))

        # Weighted Gross Score
        gross_score = (
            (liq_score * 0.25)
            + (vol_score * 0.35)
            + (buy_score * 0.25)
            + (holder_score * 0.15)
        )

        # 5. Risk Deductions & Penalty Matrix
        penalties = 0.0
        risk_flags: list[str] = []
        breakdown: list[dict[str, Any]] = []

        # Rule A: Pool Liquidity < $50,000 USD
        if pair.liquidity_usd < 50000.0:
            ded = 30.0
            penalties += ded
            risk_flags.append("LOW_LIQUIDITY")
            breakdown.append({"flag": "LOW_LIQUIDITY", "deduction": -ded, "reason": "DEX liquidity pool below $50k threshold"})

        # Rule B: Token pair age < 48 hours
        if pair.age_hours < 48.0:
            ded = 25.0
            penalties += ded
            risk_flags.append("VERY_NEW")
            breakdown.append({"flag": "VERY_NEW", "deduction": -ded, "reason": f"Pair created {pair.age_hours:.1f}h ago (< 48h)"})

        # Rule C: Top 10 holders control > 70% supply
        if top_10_holders_pct > 70.0:
            ded = 25.0
            penalties += ded
            risk_flags.append("HIGH_CONCENTRATION")
            breakdown.append({"flag": "HIGH_CONCENTRATION", "deduction": -ded, "reason": f"Top 10 holders own {top_10_holders_pct:.1f}% of supply"})

        # Rule D: Heavy Sell Pressure (Buys < 38% of total volume)
        if pair.buy_pressure_ratio < 0.38:
            ded = 15.0
            penalties += ded
            risk_flags.append("SELL_PRESSURE")
            breakdown.append({"flag": "SELL_PRESSURE", "deduction": -ded, "reason": f"Severe sell pressure (buys only {pair.buy_pressure_ratio*100:.1f}%)"})

        # Net Opportunity Score
        final_score = max(0.0, min(100.0, gross_score - penalties))

        # Risk Classification
        if penalties >= 40.0:
            risk_level = "CRITICAL"
        elif penalties >= 20.0:
            risk_level = "HIGH"
        elif penalties > 0.0:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"

        return MemeAuditRecord(
            symbol=pair.base_token_symbol,
            name=pair.base_token_name,
            chain_id=pair.chain_id,
            dex_id=pair.dex_id,
            pair_address=pair.pair_address,
            price_usd=pair.price_usd,
            liquidity_usd=pair.liquidity_usd,
            volume_24h_usd=pair.volume_24h_usd,
            volume_acceleration_1h=round(accel_1h, 2),
            volume_acceleration_5m=round(accel_5m, 2),
            buy_pressure_ratio=pair.buy_pressure_ratio,
            pair_age_hours=pair.age_hours,
            top_10_holders_pct=top_10_holders_pct,
            holder_count=holder_count,
            liquidity_score=round(liq_score, 1),
            volume_momentum_score=round(vol_score, 1),
            buy_pressure_score=round(buy_score, 1),
            holder_distribution_score=round(holder_score, 1),
            gross_score=round(gross_score, 1),
            total_penalties=round(penalties, 1),
            opportunity_score=round(final_score, 1),
            risk_level=risk_level,
            risk_flags=risk_flags,
            penalties_breakdown=breakdown,
        )

    async def scan_meme_tokens(self, symbols: list[str] | None = None) -> list[MemeAuditRecord]:
        """Scan active meme universe and rank by opportunity score with risk audits."""
        target_symbols = symbols or ["DOGE", "PEPE", "SHIB", "BONK", "WIF", "FLOKI"]
        records: list[MemeAuditRecord] = []

        holder_mocks = {
            "DOGE": (42.0, 5200000),
            "PEPE": (48.0, 310000),
            "SHIB": (55.0, 1400000),
            "BONK": (58.0, 780000),
            "WIF": (62.0, 185000),
            "FLOKI": (64.0, 490000),
        }

        for sym in target_symbols:
            pairs = await self.provider.search_pairs(sym)
            if not pairs:
                continue
            # Pick highest liquidity pair
            best_pair = max(pairs, key=lambda p: p.liquidity_usd)
            top10, h_count = holder_mocks.get(sym.upper(), (65.0, 25000))
            audit = self.analyze_pair(best_pair, top_10_holders_pct=top10, holder_count=h_count)
            records.append(audit)

        # Sort descending by opportunity score
        records.sort(key=lambda r: r.opportunity_score, reverse=True)
        return records
