"""Unit tests for realistic execution friction, slippage, and bracket triggers."""

import pytest

from src.backtesting.execution import ExecutionSimulator
from src.backtesting.models import OrderSide, SlippageModelType


def test_spread_estimation() -> None:
    sim = ExecutionSimulator(default_spread_bps=5.0)

    # Default fallback
    assert sim.estimate_spread_bps() == 5.0

    # Explicit feature spread override
    assert sim.estimate_spread_bps(feature_spread_bps=12.5) == 12.5

    # Volatility / ATR widening
    widened = sim.estimate_spread_bps(atr_14_pct=5.0)
    assert widened == 5.0 + (5.0 * 2.0)  # 15.0 bps


def test_slippage_models() -> None:
    # 1. NONE model
    sim_none = ExecutionSimulator(slippage_model=SlippageModelType.NONE)
    assert sim_none.calculate_slippage_pct(order_value_usd=10000.0, volume_24h_usd=1000000.0) == 0.0

    # 2. FIXED_BPS model
    sim_fixed = ExecutionSimulator(slippage_model=SlippageModelType.FIXED_BPS, fixed_slippage_bps=10.0)
    assert sim_fixed.calculate_slippage_pct(order_value_usd=10000.0, volume_24h_usd=1000000.0) == 0.0010  # 10 bps

    # 3. MARKET_IMPACT (Square-root law)
    sim_impact = ExecutionSimulator(
        slippage_model=SlippageModelType.MARKET_IMPACT,
        impact_gamma=0.1,
    )
    # Order: $10,000, 24h Vol: $1,000,000 -> ratio = 0.01 -> sqrt = 0.1 -> slippage = 0.1 * 0.1 = 0.01 (1%)
    slip = sim_impact.calculate_slippage_pct(order_value_usd=10000.0, volume_24h_usd=1000000.0)
    assert pytest.approx(slip, rel=1e-3) == 0.01

    # Cap check: huge order capped at 0.05 (5%)
    huge_slip = sim_impact.calculate_slippage_pct(order_value_usd=10000000.0, volume_24h_usd=100000.0)
    assert huge_slip == 0.05


def test_calculate_fill_buy_and_sell() -> None:
    sim = ExecutionSimulator(
        maker_fee_bps=2.0,
        taker_fee_bps=5.0,
        slippage_model=SlippageModelType.FIXED_BPS,
        fixed_slippage_bps=10.0,  # 0.1%
        default_spread_bps=10.0,   # Half-spread = 5 bps = 0.05%
    )
    base_price = 100.0
    order_val = 1000.0

    # BUY: Price increases by half_spread + slippage = 0.05% + 0.1% = 0.15% -> 100.15
    fill_buy, spread_cost, slip_cost, fee_usd = sim.calculate_fill(
        side=OrderSide.BUY,
        base_price=base_price,
        order_value_usd=order_val,
        volume_24h_usd=500000.0,
        is_maker=False,
    )
    assert pytest.approx(fill_buy, rel=1e-4) == 100.15
    assert pytest.approx(spread_cost, rel=1e-4) == 0.50
    assert pytest.approx(slip_cost, rel=1e-4) == 1.00
    assert pytest.approx(fee_usd, rel=1e-4) == 0.50  # 5 bps taker fee

    # SELL: Price decreases by 0.15% -> 99.85
    fill_sell, _, _, maker_fee = sim.calculate_fill(
        side=OrderSide.SELL,
        base_price=base_price,
        order_value_usd=order_val,
        volume_24h_usd=500000.0,
        is_maker=True,
    )
    assert pytest.approx(fill_sell, rel=1e-4) == 99.85
    assert pytest.approx(maker_fee, rel=1e-4) == 0.20  # 2 bps maker fee


def test_bracket_triggers() -> None:
    sim = ExecutionSimulator()
    entry = 100.0

    # Case 1: No trigger when price stays in range
    res = sim.check_bracket_triggers(
        entry_price=entry,
        candle_high=105.0,
        candle_low=95.0,
        stop_loss_pct=0.10,   # SL at 90
        take_profit_pct=0.20, # TP at 120
    )
    assert res is None

    # Case 2: Stop Loss triggered (Low breached 90.0)
    res_sl = sim.check_bracket_triggers(
        entry_price=entry,
        candle_high=102.0,
        candle_low=88.0,
        stop_loss_pct=0.10,
        take_profit_pct=0.20,
    )
    assert res_sl is not None
    assert res_sl[0] == "STOP_LOSS"
    assert res_sl[1] == 90.0

    # Case 3: Take Profit triggered (High breached 120.0)
    res_tp = sim.check_bracket_triggers(
        entry_price=entry,
        candle_high=125.0,
        candle_low=98.0,
        stop_loss_pct=0.10,
        take_profit_pct=0.20,
    )
    assert res_tp is not None
    assert res_tp[0] == "TAKE_PROFIT"
    assert res_tp[1] == 120.0
