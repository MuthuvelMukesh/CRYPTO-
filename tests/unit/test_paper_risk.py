"""Unit tests for virtual paper trading risk management engine."""

from src.paper.models import PaperOrderSide
from src.paper.risk import RiskEngine


def test_sell_order_validation() -> None:
    risk = RiskEngine()
    open_positions = [{"symbol": "BTC", "asset_class": "CORE", "market_value": 20000.0}]

    # Sell for held asset passes
    res_ok = risk.validate_order(
        side=PaperOrderSide.SELL,
        asset_symbol="BTC",
        asset_class="CORE",
        order_value_usd=10000.0,
        cash_balance=80000.0,
        total_equity=100000.0,
        open_positions=open_positions,
    )
    assert res_ok.passed is True

    # Sell for unheld asset rejected
    res_fail = risk.validate_order(
        side=PaperOrderSide.SELL,
        asset_symbol="SOL",
        asset_class="ALTCOIN",
        order_value_usd=5000.0,
        cash_balance=80000.0,
        total_equity=100000.0,
        open_positions=open_positions,
    )
    assert res_fail.passed is False
    assert "NO_POSITION_TO_SELL" in res_fail.violations


def test_cash_sufficiency_and_buffer() -> None:
    risk = RiskEngine(cash_buffer_pct=2.0)  # Reserve $2,000 on $100,000 equity

    # Cash: $10,000. Usable: $10,000 - $2,000 = $8,000
    res_ok = risk.validate_order(
        side=PaperOrderSide.BUY,
        asset_symbol="BTC",
        asset_class="CORE",
        order_value_usd=7500.0,
        cash_balance=10000.0,
        total_equity=100000.0,
        open_positions=[],
    )
    assert res_ok.passed is True

    # Order for $8,500 violates the $2,000 buffer
    res_fail = risk.validate_order(
        side=PaperOrderSide.BUY,
        asset_symbol="BTC",
        asset_class="CORE",
        order_value_usd=8500.0,
        cash_balance=10000.0,
        total_equity=100000.0,
        open_positions=[],
    )
    assert res_fail.passed is False
    assert "INSUFFICIENT_CASH" in res_fail.violations


def test_single_position_cap() -> None:
    risk = RiskEngine(max_single_position_pct=25.0)  # Max $25,000 per asset on $100k equity

    # Already holding $20,000 in SOL
    open_positions = [{"symbol": "SOL", "asset_class": "ALTCOIN", "market_value": 20000.0}]

    # Adding $4,000 -> Total $24,000 (24%) -> OK
    res_ok = risk.validate_order(
        side=PaperOrderSide.BUY,
        asset_symbol="SOL",
        asset_class="ALTCOIN",
        order_value_usd=4000.0,
        cash_balance=80000.0,
        total_equity=100000.0,
        open_positions=open_positions,
    )
    assert res_ok.passed is True

    # Adding $6,000 -> Total $26,000 (26%) -> Violates 25% cap
    res_fail = risk.validate_order(
        side=PaperOrderSide.BUY,
        asset_symbol="SOL",
        asset_class="ALTCOIN",
        order_value_usd=6000.0,
        cash_balance=80000.0,
        total_equity=100000.0,
        open_positions=open_positions,
    )
    assert res_fail.passed is False
    assert "SINGLE_POSITION_LIMIT_EXCEEDED" in res_fail.violations


def test_meme_exposure_cap() -> None:
    risk = RiskEngine(max_meme_exposure_pct=5.0)  # Max $5,000 total meme on $100k equity

    # Already holding $3,000 in PEPE
    open_positions = [{"symbol": "PEPE", "asset_class": "MEME", "market_value": 3000.0, "is_meme": True}]

    # Adding $1,500 in DOGE -> Total $4,500 (4.5%) -> OK
    res_ok = risk.validate_order(
        side=PaperOrderSide.BUY,
        asset_symbol="DOGE",
        asset_class="MEME",
        order_value_usd=1500.0,
        cash_balance=80000.0,
        total_equity=100000.0,
        open_positions=open_positions,
    )
    assert res_ok.passed is True

    # Adding $3,000 in DOGE -> Total $6,000 (6%) -> Exceeds 5% cap
    res_fail = risk.validate_order(
        side=PaperOrderSide.BUY,
        asset_symbol="DOGE",
        asset_class="MEME",
        order_value_usd=3000.0,
        cash_balance=80000.0,
        total_equity=100000.0,
        open_positions=open_positions,
    )
    assert res_fail.passed is False
    assert "MEME_EXPOSURE_LIMIT_EXCEEDED" in res_fail.violations


def test_circuit_breaker_drawdown_limit() -> None:
    risk = RiskEngine(max_drawdown_limit_pct=15.0)

    # 10% drawdown: Buying allowed
    res_ok = risk.validate_order(
        side=PaperOrderSide.BUY,
        asset_symbol="BTC",
        asset_class="CORE",
        order_value_usd=5000.0,
        cash_balance=90000.0,
        total_equity=90000.0,
        open_positions=[],
        current_drawdown_pct=10.0,
    )
    assert res_ok.passed is True

    # 18% drawdown: Circuit breaker tripped, buying rejected
    res_fail = risk.validate_order(
        side=PaperOrderSide.BUY,
        asset_symbol="BTC",
        asset_class="CORE",
        order_value_usd=5000.0,
        cash_balance=82000.0,
        total_equity=82000.0,
        open_positions=[],
        current_drawdown_pct=18.0,
    )
    assert res_fail.passed is False
    assert "CIRCUIT_BREAKER_ACTIVE" in res_fail.violations
