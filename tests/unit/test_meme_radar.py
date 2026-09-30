"""Unit tests for Meme Radar scoring engine and penalty matrix."""


from src.ingestion.providers.dexscreener_provider import DexPairMetrics
from src.scoring.meme_radar import MemeRadarEngine


def test_meme_radar_healthy_token() -> None:
    engine = MemeRadarEngine()

    healthy_pair = DexPairMetrics(
        chain_id="solana",
        dex_id="raydium",
        pair_address="pair_healthy",
        base_token_symbol="BONK",
        base_token_name="Bonk",
        quote_token_symbol="USDC",
        price_usd=0.000025,
        liquidity_usd=5000000.0,
        volume_24h_usd=15000000.0,
        volume_1h_usd=800000.0,
        volume_5m_usd=60000.0,
        txns_24h_buys=3000,
        txns_24h_sells=2000,
        buy_pressure_ratio=0.60,
        age_hours=250.0,  # > 48h
    )

    audit = engine.analyze_pair(healthy_pair, top_10_holders_pct=45.0, holder_count=50000)
    assert audit.symbol == "BONK"
    assert audit.risk_level == "LOW"
    assert len(audit.risk_flags) == 0
    assert audit.total_penalties == 0.0
    assert audit.opportunity_score > 60.0


def test_meme_radar_penalties_matrix() -> None:
    engine = MemeRadarEngine()

    # Highly risky pair: low liquidity ($20k), brand new (12h), high concentration (85%), heavy sells (25% buys)
    risky_pair = DexPairMetrics(
        chain_id="solana",
        dex_id="raydium",
        pair_address="pair_risky",
        base_token_symbol="RISKY",
        base_token_name="RiskyInu",
        quote_token_symbol="SOL",
        price_usd=0.001,
        liquidity_usd=20000.0,  # < $50k -> LOW_LIQUIDITY (-30)
        volume_24h_usd=100000.0,
        volume_1h_usd=4000.0,
        volume_5m_usd=300.0,
        txns_24h_buys=100,
        txns_24h_sells=300,
        buy_pressure_ratio=0.25,  # < 0.38 -> SELL_PRESSURE (-15)
        age_hours=12.0,           # < 48h -> VERY_NEW (-25)
    )

    audit = engine.analyze_pair(risky_pair, top_10_holders_pct=85.0, holder_count=300)
    assert "LOW_LIQUIDITY" in audit.risk_flags
    assert "VERY_NEW" in audit.risk_flags
    assert "HIGH_CONCENTRATION" in audit.risk_flags
    assert "SELL_PRESSURE" in audit.risk_flags
    assert audit.total_penalties >= 80.0
    assert audit.risk_level == "CRITICAL"
    assert audit.opportunity_score <= 20.0
