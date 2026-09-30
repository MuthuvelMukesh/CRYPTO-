"""Realistic execution modeling with bid-ask spread, square-root market impact, and fee tiers."""

import math

from src.backtesting.models import OrderSide, SlippageModelType


class ExecutionSimulator:
    """Simulates realistic micro-structure friction for market orders and bracket triggers."""

    def __init__(
        self,
        maker_fee_bps: float = 2.0,
        taker_fee_bps: float = 5.0,
        slippage_model: SlippageModelType = SlippageModelType.MARKET_IMPACT,
        fixed_slippage_bps: float = 5.0,
        impact_gamma: float = 0.1,
        default_spread_bps: float = 5.0,
    ) -> None:
        self.maker_fee_bps = maker_fee_bps
        self.taker_fee_bps = taker_fee_bps
        self.slippage_model = slippage_model
        self.fixed_slippage_bps = fixed_slippage_bps
        self.impact_gamma = impact_gamma
        self.default_spread_bps = default_spread_bps

    def estimate_spread_bps(
        self,
        feature_spread_bps: float | None = None,
        atr_14_pct: float | None = None,
    ) -> float:
        """Estimate bid-ask spread in basis points."""
        if feature_spread_bps is not None and feature_spread_bps > 0:
            return float(feature_spread_bps)

        if atr_14_pct is not None and atr_14_pct > 0:
            # High volatility widens bid-ask spread
            return max(self.default_spread_bps, float(self.default_spread_bps + (atr_14_pct * 2.0)))

        return self.default_spread_bps

    def calculate_slippage_pct(
        self,
        order_value_usd: float,
        volume_24h_usd: float,
    ) -> float:
        """Calculate market impact slippage as a percentage using power-law square-root model.

        Slippage = gamma * sqrt(OrderValue / 24hVolume)
        """
        if self.slippage_model == SlippageModelType.NONE:
            return 0.0

        if self.slippage_model == SlippageModelType.FIXED_BPS:
            return self.fixed_slippage_bps / 10000.0

        # SlippageModelType.MARKET_IMPACT
        vol = max(volume_24h_usd, 50000.0)  # Avoid division by zero/extreme illiquidity spikes
        participation = max(0.0, order_value_usd) / vol
        raw_slippage = self.impact_gamma * math.sqrt(participation)

        # Cap slippage between 0 bps and 500 bps (5%) to prevent mathematical anomalies
        return min(max(raw_slippage, 0.0), 0.05)

    def calculate_fill(
        self,
        side: OrderSide,
        base_price: float,
        order_value_usd: float,
        volume_24h_usd: float,
        spread_bps: float | None = None,
        is_maker: bool = False,
    ) -> tuple[float, float, float, float]:
        """Compute realistic fill price, spread cost, slippage cost, and exchange fee.

        Returns:
            (fill_price, spread_cost_usd, slippage_cost_usd, fee_usd)
        """
        if base_price <= 0.0:
            raise ValueError(f"Base price must be positive, got {base_price}")

        effective_spread_bps = spread_bps if spread_bps is not None else self.default_spread_bps
        half_spread_pct = (effective_spread_bps / 2.0) / 10000.0

        slippage_pct = self.calculate_slippage_pct(order_value_usd, volume_24h_usd)

        spread_cost_usd = order_value_usd * half_spread_pct
        slippage_cost_usd = order_value_usd * slippage_pct

        total_friction_pct = half_spread_pct + slippage_pct

        if side == OrderSide.BUY:
            fill_price = base_price * (1.0 + total_friction_pct)
        else:
            fill_price = base_price * max(0.000001, 1.0 - total_friction_pct)

        fee_bps = self.maker_fee_bps if is_maker else self.taker_fee_bps
        fee_usd = order_value_usd * (fee_bps / 10000.0)

        return fill_price, spread_cost_usd, slippage_cost_usd, fee_usd

    def check_bracket_triggers(
        self,
        entry_price: float,
        candle_high: float,
        candle_low: float,
        stop_loss_pct: float | None = None,
        take_profit_pct: float | None = None,
    ) -> tuple[str, float] | None:
        """Check if intra-candle high or low triggered a stop loss or take profit.

        For LONG positions:
        - Stop Loss triggered if candle_low <= entry_price * (1 - stop_loss_pct)
        - Take Profit triggered if candle_high >= entry_price * (1 + take_profit_pct)
        """
        if entry_price <= 0:
            return None

        # Check Stop Loss first (conservative risk management assumption)
        if stop_loss_pct is not None and stop_loss_pct > 0:
            sl_price = entry_price * (1.0 - stop_loss_pct)
            if candle_low <= sl_price:
                # Filled at SL threshold price
                return ("STOP_LOSS", sl_price)

        if take_profit_pct is not None and take_profit_pct > 0:
            tp_price = entry_price * (1.0 + take_profit_pct)
            if candle_high >= tp_price:
                return ("TAKE_PROFIT", tp_price)

        return None
