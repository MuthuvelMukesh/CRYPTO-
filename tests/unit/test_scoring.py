"""Unit tests for Multi-Factor Scoring models and explainability engine."""

from datetime import UTC, datetime, timedelta

import pytest

from src.config.constants import RiskFlag
from src.scoring.altcoin import AltcoinScorer
from src.scoring.core import CoreScorer
from src.scoring.meme import MemeScorer
from src.scoring.smallcap import SmallCapScorer


class MockFeatures:
    """Mock feature object simulating calculated factor values."""
    def __init__(self, **kwargs):
        self.return_1d = kwargs.get("return_1d", 0.04)
        self.return_3d = kwargs.get("return_3d", 0.08)
        self.return_7d = kwargs.get("return_7d", 0.15)
        self.return_14d = kwargs.get("return_14d", 0.20)
        self.return_30d = kwargs.get("return_30d", 0.35)
        self.return_90d = kwargs.get("return_90d", 0.60)
        self.momentum_acceleration = kwargs.get("momentum_acceleration", 0.05)
        self.rs_btc_30d = kwargs.get("rs_btc_30d", 0.12)
        self.rs_eth_30d = kwargs.get("rs_eth_30d", 0.08)
        self.ema20_ratio = kwargs.get("ema20_ratio", 1.05)
        self.ema50_ratio = kwargs.get("ema50_ratio", 1.10)
        self.ema200_ratio = kwargs.get("ema200_ratio", 1.25)
        self.adx_14 = kwargs.get("adx_14", 32.0)
        self.atr_14_pct = kwargs.get("atr_14_pct", 3.5)
        self.volume_to_20d_avg = kwargs.get("volume_to_20d_avg", 1.8)
        self.volume_acceleration = kwargs.get("volume_acceleration", 1.2)
        self.turnover_ratio = kwargs.get("turnover_ratio", 0.08)
        self.spread_est_bps = kwargs.get("spread_est_bps", 6.0)
        self.realized_vol_30d = kwargs.get("realized_vol_30d", 0.65)
        self.max_drawdown_90d = kwargs.get("max_drawdown_90d", 18.0)


class MockTokenomics:
    def __init__(self, **kwargs):
        self.fdv_to_market_cap_ratio = kwargs.get("fdv_to_market_cap_ratio", 1.2)
        self.next_unlock_date = kwargs.get("next_unlock_date", None)


class MockHolderMetrics:
    def __init__(self, **kwargs):
        self.holder_count = kwargs.get("holder_count", 50000)
        self.holder_growth_24h_pct = kwargs.get("holder_growth_24h_pct", 2.5)
        self.top_10_holders_pct = kwargs.get("top_10_holders_pct", 35.0)


def test_core_scorer_btc():
    """Verify CoreScorer produces explainable scores for BTC."""
    scorer = CoreScorer()
    features = MockFeatures()
    card = scorer.calculate_score("BTC", features)

    assert 0.0 <= card.opportunity_score <= 100.0
    assert 0.0 <= card.quality_score <= 100.0
    assert 0.0 <= card.risk_score <= 100.0
    assert "momentum" in card.components
    assert "relative_strength" in card.components
    assert "trend" in card.components
    assert "volume" in card.components
    assert "liquidity" in card.components
    assert "fundamentals" in card.components

    # Verify explainability: sum of contributions equals gross opportunity score
    gross_score = sum(c.contribution for c in card.components.values())
    total_deductions = sum(p.deduction for p in card.penalties)
    assert pytest.approx(card.opportunity_score, 0.1) == max(0.0, min(100.0, gross_score + total_deductions))
    assert len(card.explainability_summary) > 0


def test_altcoin_scorer_and_tokenomics_penalty():
    """Verify AltcoinScorer triggers FDV overhang and unlock penalties."""
    scorer = AltcoinScorer()
    features = MockFeatures()

    # Overhang: FDV / Market Cap = 5.5x, unlock in 24 hours
    unlock_time = datetime.now(UTC) + timedelta(hours=24)
    tokenomics = MockTokenomics(
        fdv_to_market_cap_ratio=5.5,
        next_unlock_date=unlock_time,
    )

    card = scorer.calculate_score("ALT_HIGH_FDV", features, tokenomics=tokenomics)
    assert 0.0 <= card.opportunity_score <= 100.0
    assert "SUPPLY_RISK" in card.risk_flags
    assert "UPCOMING_UNLOCK_48H" in card.risk_flags
    assert len(card.penalties) >= 2


def test_smallcap_scorer():
    """Verify SmallCapScorer produces valid scores and handles wide spreads."""
    scorer = SmallCapScorer()
    features = MockFeatures(spread_est_bps=75.0)  # Wide spread
    holders = MockHolderMetrics(top_10_holders_pct=72.0)  # High concentration

    card = scorer.calculate_score("SMALL_COIN", features, holder_metrics=holders)
    assert 0.0 <= card.opportunity_score <= 100.0
    assert "LOW_LIQUIDITY" in card.risk_flags
    assert "HIGH_CONCENTRATION" in card.risk_flags


def test_meme_scorer_penalty_matrix():
    """Verify MemeScorer flags extreme volatility, abnormal volume, and concentration."""
    scorer = MemeScorer()
    features = MockFeatures(
        realized_vol_30d=2.8,        # 280% vol -> EXTREME_VOLATILITY
        volume_to_20d_avg=14.0,      # 14x vol -> ABNORMAL_VOLUME
        spread_est_bps=120.0,        # 120 bps -> LOW_LIQUIDITY
    )
    holders = MockHolderMetrics(
        top_10_holders_pct=68.0,     # >60% -> HIGH_CONCENTRATION
    )

    card = scorer.calculate_score("MEME_PUMP", features, holder_metrics=holders)
    assert 0.0 <= card.opportunity_score <= 100.0
    assert RiskFlag.EXTREME_VOLATILITY.value in card.risk_flags
    assert RiskFlag.ABNORMAL_VOLUME.value in card.risk_flags
    assert RiskFlag.LOW_LIQUIDITY.value in card.risk_flags
    assert RiskFlag.HIGH_CONCENTRATION.value in card.risk_flags

    # Due to severe penalties, opportunity score should be significantly reduced
    assert card.opportunity_score < 50.0


def test_missing_features_do_not_crash():
    """Verify scoring models gracefully handle missing (None/empty) feature attributes."""
    scorer = CoreScorer()
    # Empty features object with all attributes as None
    class EmptyFeatures:
        pass

    empty_feat = EmptyFeatures()
    card = scorer.calculate_score("EMPTY_COIN", empty_feat)
    assert 0.0 <= card.opportunity_score <= 100.0
    assert 0.0 <= card.quality_score <= 100.0
