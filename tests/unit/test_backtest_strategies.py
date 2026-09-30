"""Unit tests for systematic quantitative strategies and signal generation."""

from datetime import datetime

import pytest

from src.backtesting.models import SignalAction
from src.backtesting.strategies import (
    STRATEGY_REGISTRY,
    FactorRankStrategy,
    MomentumBreakoutStrategy,
    RelativeStrengthRotationStrategy,
    TrendRegimeStrategy,
    get_strategy,
)


def test_strategy_registry() -> None:
    assert "MomentumBreakout" in STRATEGY_REGISTRY
    assert "TrendRegimeFilter" in STRATEGY_REGISTRY
    assert "RelativeStrengthRotation" in STRATEGY_REGISTRY
    assert "FactorRankModel" in STRATEGY_REGISTRY

    strat = get_strategy("MomentumBreakout", parameters={"top_n_assets": 3})
    assert isinstance(strat, MomentumBreakoutStrategy)
    assert strat.parameters["top_n_assets"] == 3

    with pytest.raises(ValueError, match="Unknown strategy 'NonExistent'"):
        get_strategy("NonExistent")


def test_momentum_strategy_signals() -> None:
    strat = MomentumBreakoutStrategy(parameters={"top_n_assets": 2, "min_return_30d": 0.05, "min_rvol": 1.0})
    now = datetime(2023, 6, 1)

    universe = {
        "BTC": {"return_30d": 0.10, "volume_to_20d_avg": 1.5, "volatility_adjusted_momentum": 2.0},
        "ETH": {"return_30d": 0.08, "volume_to_20d_avg": 1.2, "volatility_adjusted_momentum": 1.5},
        "SOL": {"return_30d": 0.02, "volume_to_20d_avg": 1.8, "volatility_adjusted_momentum": 0.5},  # Low return
        "DOGE": {"return_30d": 0.15, "volume_to_20d_avg": 0.5, "volatility_adjusted_momentum": 2.5}, # Low RVOL
    }

    positions = {
        "SOL": {"quantity": 10.0, "entry_price": 20.0, "current_price": 22.0},  # currently held
    }

    signals = strat.generate_signals(
        current_time=now,
        universe_snapshot=universe,
        current_positions=positions,
        cash=50000.0,
        total_equity=100000.0,
    )

    # SOL should be exited because it's not in top 2 candidates
    sol_signals = [s for s in signals if s.asset_id == "SOL"]
    assert len(sol_signals) == 1
    assert sol_signals[0].action == SignalAction.SELL

    # BTC and ETH should be bought with 50% target weight each
    buy_signals = [s for s in signals if s.action in (SignalAction.BUY, SignalAction.REBALANCE)]
    buy_assets = {s.asset_id for s in buy_signals}
    assert buy_assets == {"BTC", "ETH"}
    for s in buy_signals:
        assert s.target_weight == 0.5


def test_trend_regime_strategy_signals() -> None:
    strat = TrendRegimeStrategy(parameters={"benchmark_asset": "BTC", "top_n_assets": 2, "min_adx": 20.0})
    now = datetime(2023, 6, 1)

    positions = {
        "ETH": {"quantity": 10.0, "entry_price": 1800.0, "current_price": 1900.0},
    }

    # Case 1: Market Regime is RISK_OFF -> All open positions liquidated to cash
    universe_risk_off = {
        "BTC": {"regime": "RISK_OFF", "ema50_ratio": 0.95},
        "ETH": {"ema20_ratio": 1.05, "ema50_ratio": 1.05, "adx_14": 25.0},
    }
    signals_risk_off = strat.generate_signals(now, universe_risk_off, positions, 10000.0, 50000.0)
    assert len(signals_risk_off) == 1
    assert signals_risk_off[0].asset_id == "ETH"
    assert signals_risk_off[0].action == SignalAction.SELL
    assert "RISK_OFF" in signals_risk_off[0].reason

    # Case 2: Market Regime is RISK_ON -> Buy assets in uptrend
    universe_risk_on = {
        "BTC": {"regime": "RISK_ON", "ema50_ratio": 1.05},
        "SOL": {"ema20_ratio": 1.10, "ema50_ratio": 1.08, "adx_14": 28.0, "return_30d": 0.15},
        "AVAX": {"ema20_ratio": 1.04, "ema50_ratio": 1.02, "adx_14": 22.0, "return_30d": 0.05},
        "LINK": {"ema20_ratio": 0.95, "ema50_ratio": 0.98, "adx_14": 15.0, "return_30d": -0.05}, # Downtrend
    }
    signals_risk_on = strat.generate_signals(now, universe_risk_on, {}, 100000.0, 100000.0)
    buy_assets = {s.asset_id for s in signals_risk_on if s.action == SignalAction.BUY}
    assert buy_assets == {"SOL", "AVAX"}


def test_relative_strength_strategy_signals() -> None:
    strat = RelativeStrengthRotationStrategy(parameters={"benchmark_asset": "BTC", "top_n_assets": 2, "min_rs_btc_30d": 0.05})
    now = datetime(2023, 6, 1)

    universe = {
        "BTC": {},
        "SOL": {"rs_btc_30d": 0.20},  # +20% alpha over BTC
        "AVAX": {"rs_btc_30d": 0.12}, # +12% alpha over BTC
        "ETH": {"rs_btc_30d": -0.02}, # Underperforming BTC
    }
    signals = strat.generate_signals(now, universe, {}, 100000.0, 100000.0)
    buy_assets = {s.asset_id for s in signals if s.action == SignalAction.BUY}
    assert buy_assets == {"SOL", "AVAX"}


def test_factor_rank_strategy_with_risk_exclusions() -> None:
    strat = FactorRankStrategy(parameters={"top_n_assets": 2, "min_opportunity_score": 60.0, "exclude_risk_flags": True})
    now = datetime(2023, 6, 1)

    universe = {
        "BTC": {"opportunity_score": 85.0, "risk_flags": []},
        "SOL": {"opportunity_score": 90.0, "risk_flags": ["VERY_NEW"]}, # High score but excluded due to risk flag
        "AVAX": {"opportunity_score": 80.0, "risk_flags": []},
        "DOGE": {"opportunity_score": 50.0, "risk_flags": []}, # Below min score 60
    }
    signals = strat.generate_signals(now, universe, {}, 100000.0, 100000.0)
    buy_assets = {s.asset_id for s in signals if s.action == SignalAction.BUY}
    assert buy_assets == {"BTC", "AVAX"}
