"""Bias and Leakage validation test suite for the backtesting engine."""

import copy
from datetime import datetime, timedelta

import numpy as np

from src.backtesting.engine import BacktestEngine
from src.backtesting.models import BacktestConfig, SlippageModelType
from src.backtesting.strategies.momentum import MomentumBreakoutStrategy


def _generate_synthetic_candles(
    symbols: list[str],
    start_date: datetime,
    days: int = 40,
    seed: int = 42,
) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """Helper to generate deterministic candle and feature series for testing."""
    np.random.seed(seed)
    candles: dict[str, list[dict]] = {}
    features: dict[str, list[dict]] = {}

    for sym in symbols:
        c_list = []
        f_list = []
        curr_price = 100.0 if sym != "BTC" else 30000.0

        for d in range(days):
            t = start_date + timedelta(days=d)
            ret = float(np.random.normal(0.003, 0.02))
            open_p = curr_price
            close_p = open_p * (1.0 + ret)
            high_p = max(open_p, close_p) * 1.01
            low_p = min(open_p, close_p) * 0.99
            vol_usd = 1000000.0
            curr_price = close_p

            c_list.append({
                "time": t,
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": vol_usd / close_p,
                "volume_usd": vol_usd,
            })

            # Point-in-time features computed strictly on past
            f_list.append({
                "time": t,
                "return_30d": float(np.random.uniform(0.05, 0.20)),
                "volume_to_20d_avg": 1.5,
                "volatility_adjusted_momentum": float(np.random.uniform(0.5, 2.0)),
                "ema20_ratio": 1.02,
                "ema50_ratio": 1.05,
                "adx_14": 25.0,
                "opportunity_score": 75.0,
                "risk_flags": [],
            })

        candles[sym] = c_list
        features[sym] = f_list

    return candles, features


def test_no_future_lookahead_bias_in_backtesting() -> None:
    """Anti-Lookahead Perturbation Test.

    Modifying future candle data after cutoff time T MUST NOT change any trade entries,
    signals, or portfolio equity values prior to or at time T.
    """
    t0 = datetime(2023, 1, 1)
    symbols = ["BTC", "ETH", "SOL"]
    candles, features = _generate_synthetic_candles(symbols, t0, days=40)

    config = BacktestConfig(
        strategy_name="MomentumBreakout",
        start_date=t0,
        end_date=t0 + timedelta(days=39),
        initial_capital=100000.0,
        slippage_model=SlippageModelType.NONE,
    )
    strategy = MomentumBreakoutStrategy(parameters={"top_n_assets": 2, "min_return_30d": 0.01, "min_rvol": 1.0})

    # Run 1: Baseline backtest
    engine_base = BacktestEngine(config, strategy)
    result_base = engine_base.run(copy.deepcopy(candles), copy.deepcopy(features))

    cutoff_day = 20
    cutoff_time = t0 + timedelta(days=cutoff_day)

    # Run 2: Strongly perturb future candle prices and volumes starting at cutoff_time + 1 day
    perturbed_candles = copy.deepcopy(candles)
    perturbed_features = copy.deepcopy(features)

    for sym in symbols:
        for c in perturbed_candles[sym]:
            if c["time"] > cutoff_time:
                c["open"] *= 3.5
                c["high"] *= 4.0
                c["low"] *= 2.0
                c["close"] *= 3.5
                c["volume_usd"] *= 10.0

        for f in perturbed_features[sym]:
            if f["time"] > cutoff_time:
                f["return_30d"] = 0.99
                f["volatility_adjusted_momentum"] = 10.0

    engine_perturbed = BacktestEngine(config, strategy)
    result_perturbed = engine_perturbed.run(perturbed_candles, perturbed_features)

    # Verification: Equity points up to cutoff_time must match exactly to the penny
    base_eq_before = [e for e in result_base.equity_curve if datetime.fromisoformat(e["time"]) <= cutoff_time]
    pert_eq_before = [e for e in result_perturbed.equity_curve if datetime.fromisoformat(e["time"]) <= cutoff_time]

    assert len(base_eq_before) == len(pert_eq_before)
    for b, p in zip(base_eq_before, pert_eq_before, strict=True):
        assert b["time"] == p["time"]
        assert b["equity"] == p["equity"], f"Equity leak detected at {b['time']}! {b['equity']} != {p['equity']}"
        assert b["cash"] == p["cash"], f"Cash leak detected at {b['time']}! {b['cash']} != {p['cash']}"

    # Verification: Trades closed on or before cutoff_time must have identical entry, exit, and prices
    base_trades_before = [t for t in result_base.trades if datetime.fromisoformat(t["exit_time"]) <= cutoff_time]
    pert_trades_before = [t for t in result_perturbed.trades if datetime.fromisoformat(t["exit_time"]) <= cutoff_time]

    assert len(base_trades_before) == len(pert_trades_before)
    for b_trade, p_trade in zip(base_trades_before, pert_trades_before, strict=True):
        assert b_trade["asset_id"] == p_trade["asset_id"]
        assert b_trade["entry_time"] == p_trade["entry_time"]
        assert b_trade["entry_price"] == p_trade["entry_price"]
        assert b_trade["exit_price"] == p_trade["exit_price"]
        assert b_trade["pnl_usd"] == p_trade["pnl_usd"]


def test_no_same_bar_lookahead_bias() -> None:
    """Same-Bar Look-Ahead Bias Verification.

    Signals computed at the close of bar T using bar T's features and close price
    must ONLY be filled at the open of bar T+1 or later.
    Fills occurring at or before time T (entry_time <= T) MUST NOT be altered by
    perturbing bar T's own close, high, low, or features.
    """
    t0 = datetime(2023, 1, 1)
    symbols = ["BTC", "ETH", "SOL"]
    candles, features = _generate_synthetic_candles(symbols, t0, days=30)

    # In baseline, day 10 has no trigger for SOL
    cutoff_day = 10
    cutoff_time = t0 + timedelta(days=cutoff_day)

    config = BacktestConfig(
        strategy_name="MomentumBreakout",
        start_date=t0,
        end_date=t0 + timedelta(days=29),
        initial_capital=100000.0,
        slippage_model=SlippageModelType.NONE,
    )
    strategy = MomentumBreakoutStrategy(parameters={"top_n_assets": 1, "min_return_30d": 0.50})

    # Run 1: Baseline
    engine_base = BacktestEngine(config, strategy)
    result_base = engine_base.run(copy.deepcopy(candles), copy.deepcopy(features))

    # Run 2: Strongly perturb bar T's OWN close, high, low, and features for SOL at time T
    # (while keeping open price at time T identical)
    perturbed_candles = copy.deepcopy(candles)
    perturbed_features = copy.deepcopy(features)

    for c in perturbed_candles["SOL"]:
        if c["time"] == cutoff_time:
            # Bar T open is unchanged; close, high, low are spiked
            c["high"] = c["open"] * 2.0
            c["low"] = c["open"] * 0.99
            c["close"] = c["open"] * 1.8

    for f in perturbed_features["SOL"]:
        if f["time"] == cutoff_time:
            f["return_30d"] = 0.85
            f["volatility_adjusted_momentum"] = 15.0
            f["opportunity_score"] = 99.0

    engine_perturbed = BacktestEngine(config, strategy)
    result_perturbed = engine_perturbed.run(perturbed_candles, perturbed_features)

    # Trades entered at or before cutoff_time MUST NOT change!
    # Specifically, bar T's close/features cannot cause a fill at bar T's open (entry_time == cutoff_time).
    base_entries_up_to_cutoff = [
        t for t in result_base.trades if datetime.fromisoformat(t["entry_time"]) <= cutoff_time
    ]
    pert_entries_up_to_cutoff = [
        t for t in result_perturbed.trades if datetime.fromisoformat(t["entry_time"]) <= cutoff_time
    ]

    assert len(base_entries_up_to_cutoff) == len(pert_entries_up_to_cutoff), (
        f"Same-bar look-ahead detected! Perturbing bar T ({cutoff_time}) close/features "
        f"altered fills at or before T: {len(base_entries_up_to_cutoff)} baseline vs {len(pert_entries_up_to_cutoff)} perturbed."
    )
    for b_trade, p_trade in zip(base_entries_up_to_cutoff, pert_entries_up_to_cutoff, strict=True):
        assert b_trade["asset_id"] == p_trade["asset_id"]
        assert b_trade["entry_time"] == p_trade["entry_time"]
        assert b_trade["entry_price"] == p_trade["entry_price"]


def test_survivorship_bias_handling_delisted_asset() -> None:
    """Survivorship Bias Prevention Test.

    Delisted assets must be traded while active and automatically liquidated upon delisting.
    """
    t0 = datetime(2023, 1, 1)
    symbols = ["BTC", "LUNA", "ETH"]
    candles, features = _generate_synthetic_candles(symbols, t0, days=30)

    # LUNA gets delisted on day 15
    delist_time = t0 + timedelta(days=15)
    delisted_dates = {"LUNA": delist_time}

    # Make LUNA top momentum during days 0..14 so it gets bought
    for f in features["LUNA"]:
        if f["time"] < delist_time:
            f["return_30d"] = 0.50
            f["volatility_adjusted_momentum"] = 5.0
            f["volume_to_20d_avg"] = 2.0

    config = BacktestConfig(
        strategy_name="MomentumBreakout",
        start_date=t0,
        end_date=t0 + timedelta(days=29),
        initial_capital=100000.0,
    )
    strategy = MomentumBreakoutStrategy(parameters={"top_n_assets": 2})

    engine = BacktestEngine(config, strategy)
    result = engine.run(candles, features, delisted_dates=delisted_dates)

    # 1. Verify LUNA was indeed traded
    luna_trades = [t for t in result.trades if t["asset_id"] == "LUNA"]
    assert len(luna_trades) >= 1

    # 2. Verify exit reason for LUNA includes DELISTED or exited on/before delist time
    delist_exits = [t for t in luna_trades if t["exit_reason"] == "DELISTED"]
    assert len(delist_exits) >= 1
    assert datetime.fromisoformat(delist_exits[0]["exit_time"]) == delist_time
