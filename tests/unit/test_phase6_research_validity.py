"""Unit and integration test suite for Phase 6: Research Validity, Scoring Hygiene, Attribution, and Sizing."""

import math
from datetime import UTC, datetime
from types import SimpleNamespace

import numpy as np
import pytest
from httpx import AsyncClient

from src.backtesting.engine import BacktestEngine
from src.backtesting.models import BacktestConfig, SignalAction, StrategySignal
from src.backtesting.position_sizing import (
    FixedPercentSizer,
    FractionalKellySizer,
    PortfolioVolatilityGovernor,
    VolatilityTargetSizer,
)
from src.backtesting.strategies.base import BaseStrategy
from src.config.constants import DataMode
from src.research.attribution import (
    generate_attribution_report,
    generate_synthetic_attribution_dataset,
)
from src.research.ml_models import evaluate_production_gate
from src.research.statistics import (
    StrategyTrialTracker,
    bootstrap_confidence_interval,
)
from src.scoring.altcoin import AltcoinScorer
from src.scoring.base import redistribute_weights, winsorize
from src.scoring.core import CoreScorer

# ─────────────────────────────────────────────────────────────────────────────
# 1. Scoring Hygiene & Weights Versioning Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_winsorize_bounds_and_preserves_nans():
    """Verify winsorization truncates outliers without mutating in-bound values."""
    assert winsorize(15.0, 0.0, 10.0) == 10.0
    assert winsorize(-5.0, 0.0, 10.0) == 0.0
    assert winsorize(5.0, 0.0, 10.0) == 5.0
    assert winsorize(None, 0.0, 10.0) is None
    assert winsorize(float("nan"), 0.0, 10.0) is None


def test_redistribute_weights_sums_to_one():
    """Verify missing factor weights are proportionately redistributed among active factors."""
    base_w = {"a": 0.40, "b": 0.30, "c": 0.20, "d": 0.10}
    # When factor 'c' and 'd' are missing:
    active = ["a", "b"]
    new_w = redistribute_weights(base_w, active)

    assert set(new_w.keys()) == {"a", "b"}
    assert math.isclose(sum(new_w.values()), 1.0, rel_tol=1e-5)
    # Ratio between a and b should be preserved: 0.40 / 0.30 == 4/3
    assert math.isclose(new_w["a"] / new_w["b"], 4.0 / 3.0, rel_tol=1e-5)


def test_core_scorer_dynamic_redistribution_and_no_flat_baseline():
    """Ensure CoreScorer does not inject flat 65.0 when onchain metrics are missing."""
    scorer = CoreScorer()
    mock_features = SimpleNamespace(
        return_7d=0.05,
        return_30d=0.15,
        momentum_acceleration=0.01,
        rs_btc_30d=0.02,
        ema20_ratio=1.03,
        ema50_ratio=1.06,
        ema200_ratio=1.12,
        adx_14=28.0,
        volume_to_20d_avg=1.4,
        volume_acceleration=1.1,
        spread_est_bps=4.0,
        turnover_ratio=0.06,
        realized_vol_30d=0.55,
        max_drawdown_90d=15.0,
    )

    # 1. Without onchain fundamentals -> partial_data is True, no 65.0 flat baseline
    card_without = scorer.calculate_score(asset_id="BTC", features=mock_features, onchain=None)
    assert card_without.partial_data is True
    assert "fundamentals" in card_without.missing_inputs
    assert card_without.components["fundamentals"].weight == 0.0
    assert card_without.components["fundamentals"].contribution == 0.0
    assert card_without.model_version == "v3.0.0"

    # Active weights sum to 1.0
    active_weights_sum = sum(c.weight for c in card_without.components.values())
    assert math.isclose(active_weights_sum, 1.0, rel_tol=1e-3)

    # 2. With onchain fundamentals -> partial_data is False
    mock_onchain = SimpleNamespace(tvl_usd=10_000_000_000, tvl_change_7d=0.04, tx_count_24h=350_000)
    card_with = scorer.calculate_score(asset_id="BTC", features=mock_features, onchain=mock_onchain)
    assert card_with.partial_data is False
    assert len(card_with.missing_inputs) == 0
    assert card_with.components["fundamentals"].weight > 0.0
    assert card_with.components["fundamentals"].score > 0.0


def test_altcoin_scorer_no_flat_baseline_redistributes_cleanly():
    """Verify AltcoinScorer cleanly redistributes weights when tokenomics and fundamentals are absent."""
    scorer = AltcoinScorer()
    mock_features = SimpleNamespace(
        return_7d=0.08,
        return_30d=0.20,
        momentum_acceleration=0.03,
        rs_btc_30d=0.05,
        rs_eth_30d=0.03,
        ema20_ratio=1.04,
        ema50_ratio=1.08,
        adx_14=25.0,
        volume_to_20d_avg=1.6,
        volume_acceleration=1.2,
        spread_est_bps=12.0,
        turnover_ratio=0.08,
        realized_vol_30d=0.75,
        max_drawdown_90d=22.0,
    )

    card = scorer.calculate_score(asset_id="SOL", features=mock_features, tokenomics=None, onchain=None)
    assert card.partial_data is True
    assert "fundamentals" in card.missing_inputs
    assert "tokenomics_risk" in card.missing_inputs

    # Active weights sum to 1.0
    active_sum = sum(c.weight for c in card.components.values())
    assert math.isclose(active_sum, 1.0, rel_tol=1e-3)
    assert card.model_version == "v3.0.0"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Pluggable Position Sizing Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_fixed_percent_sizer():
    """Verify fixed percent sizer caps at max_position_weight."""
    sizer = FixedPercentSizer(max_position_weight=0.20)
    assert sizer.calculate_weight("BTC", signal_target_weight=0.15, portfolio_equity=100000.0) == 0.15
    # Capped at max_position_weight (0.20)
    assert sizer.calculate_weight("BTC", signal_target_weight=0.35, portfolio_equity=100000.0) == 0.20


def test_volatility_target_sizer():
    """Verify volatility targeting allocates smaller weights to higher-volatility assets."""
    sizer = VolatilityTargetSizer(max_position_weight=0.50, target_annual_vol=0.10)

    # Low vol asset (25% annual vol) -> 0.10 / 0.25 = 0.40
    w_low_vol = sizer.calculate_weight("BTC", signal_target_weight=0.50, portfolio_equity=100000.0, asset_volatility_annual=0.25)
    # High vol asset (100% annual vol) -> 0.10 / 1.00 = 0.10
    w_high_vol = sizer.calculate_weight("MEME", signal_target_weight=0.50, portfolio_equity=100000.0, asset_volatility_annual=1.00)

    assert w_low_vol > w_high_vol
    # Inverse ratio: 0.25 vol should get 4x weight compared to 1.00 vol
    assert math.isclose(w_low_vol / w_high_vol, 4.0, rel_tol=0.01)


def test_fractional_kelly_sizer():
    """Verify fractional Kelly sizes up with higher edge and down with lower edge."""
    sizer = FractionalKellySizer(max_position_weight=0.25, kelly_fraction=0.25)

    # High win rate (65%), 2.0 payoff -> strong edge
    w_high_edge = sizer.calculate_weight("BTC", signal_target_weight=0.25, portfolio_equity=100000.0, win_rate=0.65, payoff_ratio=2.0)
    # Low win rate (40%), 1.0 payoff -> negative edge -> 0 weight
    w_no_edge = sizer.calculate_weight("SHITCOIN", signal_target_weight=0.25, portfolio_equity=100000.0, win_rate=0.40, payoff_ratio=1.0)

    assert w_high_edge > 0.0
    assert w_no_edge == 0.0


def test_portfolio_volatility_governor():
    """Verify governor scales down all position sizes when aggregate volatility exceeds cap."""
    governor = PortfolioVolatilityGovernor(portfolio_vol_cap=0.20)

    weights = {"BTC": 0.20, "ETH": 0.20, "SOL": 0.20}
    asset_vols = {"BTC": 0.50, "ETH": 0.70, "SOL": 0.90}

    adjusted_w, est_vol, scale = governor.apply_cap(weights, asset_vols)

    # High vol portfolio should trigger scale factor < 1.0
    assert scale < 1.0
    assert sum(adjusted_w.values()) < sum(weights.values())

    # Governed portfolio volatility should now satisfy cap
    new_vol = governor.estimate_portfolio_volatility(adjusted_w, asset_vols)
    assert new_vol <= 0.2001


# ─────────────────────────────────────────────────────────────────────────────
# 3. Statistical Robustness & Multiple Testing Counter Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_bootstrap_confidence_interval():
    """Verify non-parametric bootstrap computes valid 95% confidence intervals."""
    rng = np.random.default_rng(42)
    sample = rng.normal(loc=10.0, scale=2.0, size=100)

    res = bootstrap_confidence_interval(sample, statistic_fn=np.mean, n_bootstrap=500, seed=42)

    assert 9.0 <= res["estimate"] <= 11.0
    assert res["ci_lower"] < res["estimate"] < res["ci_upper"]
    assert res["std_err"] > 0.0


def test_strategy_trial_tracker():
    """Verify trial tracking counts evaluated variants and computes distribution statistics."""
    tracker = StrategyTrialTracker()
    tracker.reset()

    tracker.record_trial(1.2)
    tracker.record_trial(1.8)
    tracker.record_trial(0.9)

    stats = tracker.get_distribution_stats()
    assert stats["n_trials"] == 3
    assert math.isclose(stats["mean_sharpe"], 1.3, rel_tol=0.05)
    assert stats["variance_trials"] > 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 4. Forward-Return Attribution & Synthetic Dataset Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_synthetic_attribution_known_ground_truth_ic():
    """Verify attribution engine accurately measures known ground-truth correlation (target IC)."""
    target_ic = 0.25
    scores, forward_returns = generate_synthetic_attribution_dataset(
        n_samples=1000,
        target_ic=target_ic,
        seed=42,
    )

    report = generate_attribution_report(
        scores=scores,
        forward_returns=forward_returns,
        horizon="1d",
        data_mode=DataMode.SYNTHETIC_TEST,
    )

    # Measured Spearman and Pearson IC should be within +/- 0.06 of target_ic
    assert abs(report.spearman_rank_ic - target_ic) < 0.06
    assert abs(report.pearson_ic - target_ic) < 0.06
    assert report.spearman_p_value < 0.001  # Statistically significant
    assert report.data_mode == DataMode.SYNTHETIC_TEST.value
    assert len(report.deciles) == 10
    # Decile 10 (top scores) should outperform Decile 1 (bottom scores)
    assert report.monotonicity_spread_pct > 0.0


def test_attribution_small_sample_warning():
    """Verify small sample warning triggers when observations count N < 30."""
    scores = [40.0, 60.0, 80.0, 50.0, 70.0]
    returns = [-0.02, 0.03, 0.05, 0.01, 0.04]

    report = generate_attribution_report(scores, returns, min_samples=30)
    assert report.small_sample_warning is True
    assert report.small_sample_message is not None


# ─────────────────────────────────────────────────────────────────────────────
# 5. ML Models Production Gating Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_ml_production_gate_decision():
    """Verify experimental ML model passes gate only when beating baseline out-of-sample."""
    rng = np.random.default_rng(42)
    actual_returns = rng.normal(0.01, 0.04, size=100)

    # 1. Model that beats baseline by +0.10 Rank IC
    baseline_preds = rng.normal(0.0, 1.0, size=100)
    strong_model_preds = actual_returns + rng.normal(0.0, 0.01, size=100)

    gate_pass = evaluate_production_gate(
        model_predictions=strong_model_preds,
        baseline_predictions=baseline_preds,
        actual_returns=actual_returns,
        min_ic_improvement=0.02,
    )
    assert gate_pass.passed is True
    assert gate_pass.ic_delta >= 0.02

    # 2. Model that fails to beat baseline
    weak_model_preds = rng.normal(0.0, 1.0, size=100)
    gate_fail = evaluate_production_gate(
        model_predictions=weak_model_preds,
        baseline_predictions=strong_model_preds,
        actual_returns=actual_returns,
        min_ic_improvement=0.02,
    )
    assert gate_fail.passed is False


# ─────────────────────────────────────────────────────────────────────────────
# 6. Regime-Split Backtest Engine Tests
# ─────────────────────────────────────────────────────────────────────────────


class MockRegimeStrategy(BaseStrategy):
    """Simple test strategy generating Buy signals."""

    def __init__(self) -> None:
        super().__init__(name="MockRegimeStrategy")

    def generate_signals(self, current_time, universe_snapshot, current_positions, cash, total_equity):
        signals = []
        for asset_id in universe_snapshot:
            if asset_id not in current_positions:
                signals.append(
                    StrategySignal(
                        asset_id=asset_id,
                        action=SignalAction.BUY,
                        target_weight=0.20,
                    )
                )
        return signals


def test_backtest_regime_split_and_position_sizer():
    """Verify BacktestEngine generates regime-split breakdown and executes pluggable sizing."""
    config = BacktestConfig(
        strategy_name="MockRegimeStrategy",
        start_date=datetime(2025, 1, 1, tzinfo=UTC),
        end_date=datetime(2025, 1, 20, tzinfo=UTC),
        initial_capital=100000.0,
        position_sizer="volatility_target",
        target_annual_vol=0.20,
        portfolio_vol_cap=0.25,
    )
    engine = BacktestEngine(config=config, strategy=MockRegimeStrategy())

    # Build 20 daily bars with BTC and an altcoin
    from datetime import timedelta
    candles = {"BTC": [], "SOL": []}
    features = {"BTC": [], "SOL": []}

    for i in range(20):
        dt = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=i)
        btc_price = 50000.0 * (1.02 ** i)
        sol_price = 100.0 * (1.03 ** i)

        candles["BTC"].append({"time": dt, "open": btc_price, "high": btc_price * 1.01, "low": btc_price * 0.99, "close": btc_price, "volume": 1000.0, "volume_usd": 50000000.0})
        candles["SOL"].append({"time": dt, "open": sol_price, "high": sol_price * 1.01, "low": sol_price * 0.99, "close": sol_price, "volume": 5000.0, "volume_usd": 500000.0})

        regime = "RISK_ON" if i >= 10 else "RISK_OFF"
        features["BTC"].append({"time": dt, "market_regime": regime, "realized_vol_30d": 0.40})
        features["SOL"].append({"time": dt, "market_regime": regime, "realized_vol_30d": 0.80})

    result = engine.run(candles, features)

    # Check regime breakdown
    assert "RISK_ON" in result.regime_breakdown
    assert "RISK_OFF" in result.regime_breakdown
    assert result.regime_breakdown["RISK_ON"]["duration_pct"] > 0
    assert result.regime_breakdown["RISK_OFF"]["duration_pct"] > 0

    # Check statistical robustness
    assert "sharpe_ratio" in result.statistical_robustness
    assert "sharpe_ci_95" in result.statistical_robustness
    assert len(result.statistical_robustness["sharpe_ci_95"]) == 2


# ─────────────────────────────────────────────────────────────────────────────
# 7. Research REST Endpoints Integration Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_research_api_endpoints(client: AsyncClient):
    """Verify research endpoints (/attribution, /ic, /trials, /model-gate)."""
    # 1. Attribution endpoint with synthetic test mode
    resp_attr = await client.get("/api/v1/research/attribution?synthetic=true&horizon=1d")
    assert resp_attr.status_code == 200
    attr_data = resp_attr.json()
    assert attr_data["data_mode"] == "SYNTHETIC_TEST"
    assert "pearson_ic" in attr_data
    assert "spearman_rank_ic" in attr_data
    assert len(attr_data["deciles"]) == 10

    # 2. Rolling IC endpoint
    resp_ic = await client.get("/api/v1/research/ic?synthetic=true&horizon=1d")
    assert resp_ic.status_code == 200
    ic_data = resp_ic.json()
    assert len(ic_data["points"]) > 0

    # 3. Strategy trials counter endpoint
    resp_trials = await client.get("/api/v1/research/trials")
    assert resp_trials.status_code == 200
    trials_data = resp_trials.json()
    assert "total_trials" in trials_data
    assert "expected_max_sharpe" in trials_data

    # 4. ML model gate evaluation endpoint
    gate_payload = {
        "model_predictions": [0.05, 0.08, 0.02, 0.10, 0.04, 0.09, 0.01, 0.07, 0.03, 0.06, 0.08, 0.05],
        "baseline_predictions": [0.01, 0.02, 0.01, 0.03, 0.02, 0.01, 0.02, 0.01, 0.02, 0.01, 0.02, 0.01],
        "actual_returns": [0.04, 0.07, 0.01, 0.09, 0.03, 0.08, 0.00, 0.06, 0.02, 0.05, 0.07, 0.04],
        "min_ic_improvement": 0.02,
    }
    resp_gate = await client.post("/api/v1/research/model-gate", json=gate_payload)
    assert resp_gate.status_code == 200
    gate_res = resp_gate.json()
    assert "passed" in gate_res
    assert "model_rank_ic" in gate_res
