"""Momentum breakout and volatility-adjusted momentum systematic strategy."""

from datetime import datetime
from typing import Any

from src.backtesting.models import SignalAction, StrategySignal
from src.backtesting.strategies.base import BaseStrategy


class MomentumBreakoutStrategy(BaseStrategy):
    """Systematic momentum strategy targeting top assets with expanding volume and positive risk-adjusted momentum."""

    def __init__(self, parameters: dict[str, Any] | None = None) -> None:
        params = {
            "top_n_assets": 5,
            "min_return_30d": 0.03,  # Minimum 3% positive 30D return
            "min_rvol": 1.0,         # Minimum 1.0x 20D average volume
            "stop_loss_pct": 0.08,   # 8% stop loss threshold
            "take_profit_pct": 0.25, # 25% take profit threshold
            **(parameters or {}),
        }
        super().__init__(
            name="MomentumBreakout",
            version="1.0.0",
            parameters=params,
        )

    def generate_signals(
        self,
        current_time: datetime,
        universe_snapshot: dict[str, dict[str, Any]],
        current_positions: dict[str, dict[str, Any]],
        cash: float,
        total_equity: float,
    ) -> list[StrategySignal]:
        signals: list[StrategySignal] = []
        top_n: int = int(self.parameters["top_n_assets"])
        min_ret: float = float(self.parameters["min_return_30d"])
        min_rvol: float = float(self.parameters["min_rvol"])
        stop_loss_pct: float = float(self.parameters["stop_loss_pct"])
        take_profit_pct: float = float(self.parameters["take_profit_pct"])

        # Score eligible assets
        candidates: list[tuple[str, float]] = []
        for asset_id, feat in universe_snapshot.items():
            ret_30d = feat.get("return_30d", 0.0) or 0.0
            rvol = feat.get("volume_to_20d_avg", 1.0) or 1.0
            vam = feat.get("volatility_adjusted_momentum", 0.0) or 0.0

            if ret_30d >= min_ret and rvol >= min_rvol:
                # Rank primarily by volatility-adjusted momentum, fallback to 30d return
                score = vam if vam != 0.0 else ret_30d
                candidates.append((asset_id, score))

        # Sort descending by score
        candidates.sort(key=lambda x: x[1], reverse=True)
        top_selected_ids = {asset_id for asset_id, _ in candidates[:top_n]}

        target_weight = 1.0 / top_n if top_n > 0 else 0.0

        # Check existing positions to exit if no longer in top set
        for held_asset_id in list(current_positions.keys()):
            if held_asset_id not in top_selected_ids:
                signals.append(
                    StrategySignal(
                        asset_id=held_asset_id,
                        action=SignalAction.SELL,
                        target_weight=0.0,
                        reason="Momentum rotation exit: dropped from top momentum candidates",
                    )
                )

        # Allocate to top selected assets
        for asset_id in top_selected_ids:
            signals.append(
                StrategySignal(
                    asset_id=asset_id,
                    action=SignalAction.BUY if asset_id not in current_positions else SignalAction.REBALANCE,
                    target_weight=target_weight,
                    stop_loss_pct=stop_loss_pct,
                    take_profit_pct=take_profit_pct,
                    reason=f"Top momentum candidate (target_weight={round(target_weight * 100, 1)}%)",
                )
            )

        return signals
