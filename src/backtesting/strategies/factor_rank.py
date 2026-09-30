"""Multi-factor quantitative scoring strategy with risk penalty exclusions."""

from datetime import datetime
from typing import Any

from src.backtesting.models import SignalAction, StrategySignal
from src.backtesting.strategies.base import BaseStrategy


class FactorRankStrategy(BaseStrategy):
    """Multi-factor quantitative strategy ranking assets by explainable Opportunity Score with risk filtering."""

    def __init__(self, parameters: dict[str, Any] | None = None) -> None:
        params = {
            "top_n_assets": 5,
            "min_opportunity_score": 65.0,
            "exclude_risk_flags": True,
            "stop_loss_pct": 0.08,
            "take_profit_pct": 0.30,
            **(parameters or {}),
        }
        super().__init__(
            name="FactorRankModel",
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
        min_score: float = float(self.parameters["min_opportunity_score"])
        exclude_flags: bool = bool(self.parameters["exclude_risk_flags"])
        stop_loss_pct: float = float(self.parameters["stop_loss_pct"])
        take_profit_pct: float = float(self.parameters["take_profit_pct"])

        critical_flags = {
            "VERY_NEW",
            "HIGH_CONCENTRATION",
            "LOW_LIQUIDITY",
            "SUPPLY_RISK",
            "EXTREME_VOLATILITY",
        }

        candidates: list[tuple[str, float]] = []

        for asset_id, feat in universe_snapshot.items():
            opp_score = feat.get("opportunity_score")
            # If explicit opportunity_score not precomputed in features, compute quick proxy
            if opp_score is None:
                ret = feat.get("return_30d", 0.0) or 0.0
                rs = feat.get("rs_btc_30d", 0.0) or 0.0
                ema20 = feat.get("ema20_ratio", 1.0) or 1.0
                rvol = feat.get("volume_to_20d_avg", 1.0) or 1.0
                # Proxy composite 0-100
                opp_score = 50.0 + (ret * 50.0) + (rs * 50.0) + ((ema20 - 1.0) * 100.0) + ((rvol - 1.0) * 20.0)
                opp_score = max(0.0, min(100.0, opp_score))

            if opp_score < min_score:
                continue

            risk_flags = set(feat.get("risk_flags") or [])
            if exclude_flags and (risk_flags & critical_flags):
                continue

            candidates.append((asset_id, float(opp_score)))

        candidates.sort(key=lambda x: x[1], reverse=True)
        top_selected_ids = {asset_id for asset_id, _ in candidates[:top_n]}

        target_weight = 1.0 / top_n if top_n > 0 else 0.0

        # Sell existing holdings that fell out of score threshold
        for held_asset_id in list(current_positions.keys()):
            if held_asset_id not in top_selected_ids:
                signals.append(
                    StrategySignal(
                        asset_id=held_asset_id,
                        action=SignalAction.SELL,
                        target_weight=0.0,
                        reason="Score degradation: opportunity score dropped below top rank threshold",
                    )
                )

        # Allocate to top scored assets
        for asset_id in top_selected_ids:
            signals.append(
                StrategySignal(
                    asset_id=asset_id,
                    action=SignalAction.BUY if asset_id not in current_positions else SignalAction.REBALANCE,
                    target_weight=target_weight,
                    stop_loss_pct=stop_loss_pct,
                    take_profit_pct=take_profit_pct,
                    reason=f"Top quantitative factor score (target_weight={round(target_weight * 100, 1)}%)",
                )
            )

        return signals
