"""Cross-sectional Relative Strength rotation strategy against benchmark."""

from datetime import datetime
from typing import Any

from src.backtesting.models import SignalAction, StrategySignal
from src.backtesting.strategies.base import BaseStrategy


class RelativeStrengthRotationStrategy(BaseStrategy):
    """Systematic rotation strategy selecting altcoins demonstrating persistent alpha over BTC."""

    def __init__(self, parameters: dict[str, Any] | None = None) -> None:
        params = {
            "benchmark_asset": "BTC",
            "top_n_assets": 5,
            "min_rs_btc_30d": 0.02,  # Minimum 2% outperformance over BTC
            "stop_loss_pct": 0.07,
            "take_profit_pct": 0.30,
            **(parameters or {}),
        }
        super().__init__(
            name="RelativeStrengthRotation",
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
        benchmark_id: str = str(self.parameters["benchmark_asset"])
        top_n: int = int(self.parameters["top_n_assets"])
        min_rs: float = float(self.parameters["min_rs_btc_30d"])
        stop_loss_pct: float = float(self.parameters["stop_loss_pct"])
        take_profit_pct: float = float(self.parameters["take_profit_pct"])

        candidates: list[tuple[str, float]] = []

        for asset_id, feat in universe_snapshot.items():
            if asset_id == benchmark_id:
                continue

            rs_btc = feat.get("rs_btc_30d", 0.0) or 0.0
            if rs_btc >= min_rs:
                candidates.append((asset_id, rs_btc))

        candidates.sort(key=lambda x: x[1], reverse=True)
        top_selected_ids = {asset_id for asset_id, _ in candidates[:top_n]}

        target_weight = 1.0 / top_n if top_n > 0 else 0.0

        # Sell assets that lost relative strength
        for held_asset_id in list(current_positions.keys()):
            if held_asset_id not in top_selected_ids:
                signals.append(
                    StrategySignal(
                        asset_id=held_asset_id,
                        action=SignalAction.SELL,
                        target_weight=0.0,
                        reason="Relative strength breakdown: asset no longer outperforming benchmark",
                    )
                )

        # Allocate to top outperforming altcoins
        for asset_id in top_selected_ids:
            signals.append(
                StrategySignal(
                    asset_id=asset_id,
                    action=SignalAction.BUY if asset_id not in current_positions else SignalAction.REBALANCE,
                    target_weight=target_weight,
                    stop_loss_pct=stop_loss_pct,
                    take_profit_pct=take_profit_pct,
                    reason=f"Top relative strength vs {benchmark_id} (target_weight={round(target_weight * 100, 1)}%)",
                )
            )

        return signals
