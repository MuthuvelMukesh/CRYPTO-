"""Risk management engine enforcing position caps, meme quotas, and circuit breakers."""

from src.config.constants import AssetClass
from src.paper.models import PaperOrderSide, RiskValidationResult


class RiskEngine:
    """Evaluates proposed orders against portfolio risk constraints and concentration limits."""

    def __init__(
        self,
        max_single_position_pct: float = 25.0,
        max_meme_exposure_pct: float = 5.0,
        cash_buffer_pct: float = 2.0,
        max_open_positions: int = 15,
        max_drawdown_limit_pct: float = 20.0,
    ) -> None:
        self.max_single_position_pct = max_single_position_pct
        self.max_meme_exposure_pct = max_meme_exposure_pct
        self.cash_buffer_pct = cash_buffer_pct
        self.max_open_positions = max_open_positions
        self.max_drawdown_limit_pct = max_drawdown_limit_pct

    def validate_order(
        self,
        side: PaperOrderSide,
        asset_symbol: str,
        asset_class: str,
        order_value_usd: float,
        cash_balance: float,
        total_equity: float,
        open_positions: list[dict],  # [{'symbol': str, 'asset_class': str, 'market_value': float}]
        current_drawdown_pct: float = 0.0,
    ) -> RiskValidationResult:
        """Inspect and enforce risk boundaries prior to order routing."""
        # 1. SELL orders always bypass buy risk restrictions (always allow de-risking)
        if side == PaperOrderSide.SELL:
            # Check asset is actually held
            held = next((p for p in open_positions if p["symbol"] == asset_symbol), None)
            if not held:
                return RiskValidationResult(
                    passed=False,
                    reason=f"Cannot execute SELL: no active open position in {asset_symbol}",
                    violations=["NO_POSITION_TO_SELL"],
                )
            return RiskValidationResult(passed=True)

        violations: list[str] = []

        # 2. Circuit Breaker Drawdown Rule
        if current_drawdown_pct >= self.max_drawdown_limit_pct:
            violations.append("CIRCUIT_BREAKER_ACTIVE")
            return RiskValidationResult(
                passed=False,
                reason=(
                    f"Risk Circuit Breaker: Current portfolio drawdown ({current_drawdown_pct:.1f}%) "
                    f"exceeds safety threshold ({self.max_drawdown_limit_pct:.1f}%). New buying halted."
                ),
                violations=violations,
            )

        # 3. Cash Buffer & Cash Sufficiency
        min_cash_required = total_equity * (self.cash_buffer_pct / 100.0)
        usable_cash = max(0.0, cash_balance - min_cash_required)

        if order_value_usd > usable_cash:
            violations.append("INSUFFICIENT_CASH")
            return RiskValidationResult(
                passed=False,
                reason=(
                    f"Insufficient free cash: Order value ${order_value_usd:,.2f} exceeds "
                    f"usable cash ${usable_cash:,.2f} (reserving {self.cash_buffer_pct}% cash buffer)."
                ),
                violations=violations,
            )

        # 4. Single Asset Concentration Cap (Max 25%)
        existing_val = sum(p["market_value"] for p in open_positions if p["symbol"] == asset_symbol)
        new_total_val = existing_val + order_value_usd
        max_allowed_single = total_equity * (self.max_single_position_pct / 100.0)

        if new_total_val > max_allowed_single:
            violations.append("SINGLE_POSITION_LIMIT_EXCEEDED")
            return RiskValidationResult(
                passed=False,
                reason=(
                    f"Position concentration limit: Total exposure in {asset_symbol} would reach "
                    f"${new_total_val:,.2f} ({(new_total_val / total_equity) * 100.0:.1f}%), "
                    f"exceeding maximum single allocation cap of {self.max_single_position_pct}%."
                ),
                violations=violations,
            )

        # 5. Meme Coin Exposure Cap (Max 5%)
        is_meme = (
            asset_class.upper() == AssetClass.MEME.value.upper()
            or "MEME" in asset_class.upper()
            or asset_symbol in {"DOGE", "SHIB", "PEPE", "BONK", "WIF", "FLOKI"}
        )

        if is_meme:
            existing_meme_val = sum(
                p["market_value"]
                for p in open_positions
                if p.get("is_meme") or p["symbol"] in {"DOGE", "SHIB", "PEPE", "BONK", "WIF", "FLOKI"}
            )
            new_meme_val = existing_meme_val + order_value_usd
            max_allowed_meme = total_equity * (self.max_meme_exposure_pct / 100.0)

            if new_meme_val > max_allowed_meme:
                violations.append("MEME_EXPOSURE_LIMIT_EXCEEDED")
                return RiskValidationResult(
                    passed=False,
                    reason=(
                        f"Meme exposure limit: Aggregate meme exposure would reach "
                        f"${new_meme_val:,.2f} ({(new_meme_val / total_equity) * 100.0:.1f}%), "
                        f"exceeding mandated risk cap of {self.max_meme_exposure_pct}%."
                    ),
                    violations=violations,
                )

        # 6. Max Concurrent Positions Cap
        already_held = any(p["symbol"] == asset_symbol for p in open_positions)
        if not already_held and len(open_positions) >= self.max_open_positions:
            violations.append("MAX_POSITIONS_LIMIT_EXCEEDED")
            return RiskValidationResult(
                passed=False,
                reason=f"Maximum concurrent open positions ({self.max_open_positions}) reached.",
                violations=violations,
            )

        return RiskValidationResult(passed=True)
