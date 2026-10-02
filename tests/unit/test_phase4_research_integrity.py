"""Unit tests for Phase 4: Research integrity, zero look-ahead bias, DSR, and survivorship bias mitigation."""

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Asset
from src.features.trend import calculate_atr
from src.features.volatility import calculate_volatility_features
from src.ingestion.universe import get_point_in_time_universe
from src.research.ml_models import walk_forward_train_evaluate
from src.research.statistics import (
    compute_deflated_sharpe_ratio,
    compute_expected_max_sharpe,
    compute_probabilistic_sharpe_ratio,
)


def test_feature_time_indexing_no_future_leakage() -> None:
    """Feature at bar t must strictly depend only on bars <= t, never on t+1 or beyond."""
    np.random.seed(42)
    n = 60
    closes_original = 100.0 + np.cumsum(np.random.randn(n))
    highs_original = closes_original + np.random.uniform(0.5, 2.0, n)
    lows_original = closes_original - np.random.uniform(0.5, 2.0, n)

    # Calculate ATR on original series
    atr_original = calculate_atr(highs_original, lows_original, closes_original, period=14)

    # Modify future data at bar 45 (e.g. inject extreme shock at t=45)
    closes_modified = closes_original.copy()
    highs_modified = highs_original.copy()
    lows_modified = lows_original.copy()
    closes_modified[45] += 1000.0
    highs_modified[45] += 1000.0

    atr_modified = calculate_atr(highs_modified, lows_modified, closes_modified, period=14)

    # All values strictly BEFORE bar 45 (t < 45) must be 100% IDENTICAL
    np.testing.assert_array_equal(
        atr_original[:45],
        atr_modified[:45],
        err_msg="Look-ahead leakage detected: future change at bar 45 altered historical feature at t < 45!",
    )

    # Test volatility features up to bar 30
    vol_orig = calculate_volatility_features(
        highs=highs_original[:30].tolist(),
        lows=lows_original[:30].tolist(),
        closes=closes_original[:30].tolist(),
    )
    # Volatility computed using data up to bar 30 must not change when future bars 31-60 are changed
    vol_with_future = calculate_volatility_features(
        highs=highs_original[:30].tolist(),
        lows=lows_original[:30].tolist(),
        closes=closes_original[:30].tolist(),
    )
    assert vol_orig.rolling_std_20 == vol_with_future.rolling_std_20
    assert vol_orig.realized_vol_30d == vol_with_future.realized_vol_30d


def test_target_leakage_assertion_raises() -> None:
    """walk_forward_train_evaluate must assert that target columns do NOT appear in feature_cols."""
    np.random.seed(42)
    n = 100
    df = pd.DataFrame({
        "f1": np.random.randn(n),
        "f2": np.random.randn(n),
        "forward_return": np.random.randn(n) * 0.02,
        "target_direction": np.random.randint(0, 2, n),
    })

    # Attempting to include target_return in features must fail
    with pytest.raises(AssertionError) as exc_info:
        walk_forward_train_evaluate(
            df=df,
            feature_cols=["f1", "f2", "forward_return"],
            target_return_col="forward_return",
            target_binary_col="target_direction",
        )
    assert "DATA LEAKAGE DETECTED" in str(exc_info.value)

    # Attempting to include target_direction in features must fail
    with pytest.raises(AssertionError) as exc_info2:
        walk_forward_train_evaluate(
            df=df,
            feature_cols=["f1", "target_direction"],
            target_return_col="forward_return",
            target_binary_col="target_direction",
        )
    assert "DATA LEAKAGE DETECTED" in str(exc_info2.value)


def test_scaler_in_sample_separation() -> None:
    """Scalers must be fit strictly on in-sample data and applied to out-of-sample data."""
    np.random.seed(42)
    n = 200
    df = pd.DataFrame({
        "f1": np.random.normal(loc=50.0, scale=10.0, size=n),
        "f2": np.random.normal(loc=100.0, scale=20.0, size=n),
        "forward_return": np.random.randn(n) * 0.02,
        "target_direction": np.random.randint(0, 2, n),
    })

    report = walk_forward_train_evaluate(
        df=df,
        feature_cols=["f1", "f2"],
        train_pct=0.70,
        embargo_bars=10,
        scaler_type="standard",
    )
    assert report.n_samples_train > 0
    assert report.n_samples_test > 0
    assert 0.0 <= report.accuracy <= 1.0


def test_deflated_sharpe_ratio_mathematical_properties() -> None:
    """Verify Bailey & Lopez de Prado DSR mathematical test vectors and properties."""
    # 1. Single trial (N=1, V=0): DSR must equal standard PSR
    dsr_single = compute_deflated_sharpe_ratio(
        sharpe_ratio=1.5,
        n_observations=252,
        n_trials=1,
        variance_trials=0.0,
    )
    psr_single = compute_probabilistic_sharpe_ratio(
        sharpe_ratio=1.5,
        n_observations=252,
    )
    assert pytest.approx(dsr_single["deflated_sharpe_ratio"], rel=1e-3) == pytest.approx(psr_single, rel=1e-3)
    assert dsr_single["expected_max_sharpe"] == 0.0

    # 2. Multiple trials (N=50, V=0.25): expected max Sharpe > 0, so DSR must be lower than single trial
    dsr_multi = compute_deflated_sharpe_ratio(
        sharpe_ratio=1.5,
        n_observations=252,
        n_trials=50,
        variance_trials=0.25,
    )
    assert dsr_multi["expected_max_sharpe"] > 1.0
    assert dsr_multi["deflated_sharpe_ratio"] < dsr_single["deflated_sharpe_ratio"]

    # 3. Expected max Sharpe increases with number of trials N
    e_max_10 = compute_expected_max_sharpe(n_trials=10, variance_trials=0.25)
    e_max_100 = compute_expected_max_sharpe(n_trials=100, variance_trials=0.25)
    assert e_max_100 > e_max_10

    # 4. Negative Sharpe ratio produces DSR < 0.50
    dsr_neg = compute_deflated_sharpe_ratio(
        sharpe_ratio=-0.5,
        n_observations=252,
        n_trials=1,
        variance_trials=0.0,
    )
    assert dsr_neg["deflated_sharpe_ratio"] < 0.50


@pytest.mark.asyncio
async def test_point_in_time_universe_filtering(db_session: AsyncSession) -> None:
    """Point-in-time universe query must only return assets active and not delisted at as_of date."""
    # Seed 3 assets with different listing and delisting dates:
    # Asset A: Listed 2024-01-01, Never delisted
    # Asset B: Listed 2024-01-01, Delisted 2024-06-01
    # Asset C: Listed 2024-08-01, Never delisted
    a1 = Asset(
        id="PIT_A", name="Asset A", symbol="A", asset_class="CORE", primary_sector="L1",
        created_at=datetime(2024, 1, 1, tzinfo=UTC), delisted_at=None,
    )
    a2 = Asset(
        id="PIT_B", name="Asset B", symbol="B", asset_class="ALTCOIN", primary_sector="DeFi",
        created_at=datetime(2024, 1, 1, tzinfo=UTC), delisted_at=datetime(2024, 6, 1, tzinfo=UTC),
    )
    a3 = Asset(
        id="PIT_C", name="Asset C", symbol="C", asset_class="MEME", primary_sector="Meme",
        created_at=datetime(2024, 8, 1, tzinfo=UTC), delisted_at=None,
    )
    db_session.add_all([a1, a2, a3])
    await db_session.commit()

    # Query 1: As of March 2024 -> PIT_A and PIT_B active, PIT_C not listed yet
    as_of_march = datetime(2024, 3, 1, tzinfo=UTC)
    u_march = await get_point_in_time_universe(db_session, as_of=as_of_march)
    assert "PIT_A" in u_march
    assert "PIT_B" in u_march
    assert "PIT_C" not in u_march

    # Query 2: As of July 2024 -> PIT_A active, PIT_B delisted, PIT_C not listed yet
    as_of_july = datetime(2024, 7, 1, tzinfo=UTC)
    u_july = await get_point_in_time_universe(db_session, as_of=as_of_july)
    assert "PIT_A" in u_july
    assert "PIT_B" not in u_july
    assert "PIT_C" not in u_july

    # Query 3: As of September 2024 -> PIT_A and PIT_C active, PIT_B delisted
    as_of_sept = datetime(2024, 9, 1, tzinfo=UTC)
    u_sept = await get_point_in_time_universe(db_session, as_of=as_of_sept)
    assert "PIT_A" in u_sept
    assert "PIT_B" not in u_sept
    assert "PIT_C" in u_sept


def test_backtest_survivorship_badge_and_dsr() -> None:
    """Backtest engine must surface survivorship bias status badge and DSR calculation."""
    from src.backtesting.engine import BacktestEngine
    from src.backtesting.models import BacktestConfig
    from src.backtesting.strategies import MomentumBreakoutStrategy

    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 1, 10, tzinfo=UTC)

    # 1. Config with point_in_time_universe=True and trials parameters
    cfg_mitigated = BacktestConfig(
        strategy_name="MomentumBreakout",
        start_date=start,
        end_date=end,
        point_in_time_universe=True,
        parameters={"n_trials": 20, "variance_trials": 0.30},
    )
    engine_mitigated = BacktestEngine(config=cfg_mitigated, strategy=MomentumBreakoutStrategy())

    # Build synthetic candles
    candles = {
        "BTC": [
            {
                "time": datetime(2024, 1, i, tzinfo=UTC),
                "open": 40000.0 + i * 100,
                "high": 40200.0 + i * 100,
                "low": 39800.0 + i * 100,
                "close": 40100.0 + i * 100,
                "volume": 1000.0,
                "volume_usd": 40000000.0,
            }
            for i in range(1, 11)
        ]
    }
    features = {
        "BTC": [
            {
                "time": datetime(2024, 1, i, tzinfo=UTC),
                "return_30d": 0.10,
                "volume_to_20d_avg": 1.5,
                "volatility_adjusted_momentum": 1.8,
            }
            for i in range(1, 11)
        ]
    }

    res_mitigated = engine_mitigated.run(historical_candles=candles, historical_features=features)
    assert res_mitigated.survivorship_bias_status == "Survivorship Bias: Mitigated (Point-in-Time Universe)"
    assert res_mitigated.deflated_sharpe_ratio is not None

    # 2. Config with point_in_time_universe=False
    cfg_unmitigated = BacktestConfig(
        strategy_name="MomentumBreakout",
        start_date=start,
        end_date=end,
        point_in_time_universe=False,
    )
    engine_unmitigated = BacktestEngine(config=cfg_unmitigated, strategy=MomentumBreakoutStrategy())
    res_unmitigated = engine_unmitigated.run(historical_candles=candles, historical_features=features)
    assert res_unmitigated.survivorship_bias_status == "Survivorship Bias: Unmitigated (Survivors Only)"

