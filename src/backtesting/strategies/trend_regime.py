"""Trend-following systematic strategy with macro market regime filter."""

from datetime import datetime
from typing import Any

from src.backtesting.models import SignalAction, StrategySignal
from src.backtesting.strategies.base import BaseStrategy


class TrendRegimeStrategy(BaseStrategy):
    """Trend-following strategy that aggressively de-risks to cash when market regime turns RISK_OFF."""

    def __init__(self, parameters: dict[str, Any] | None = None) -> None:
        params = {
            "benchmark_asset": "BTC",
            "top_n_assets": 4,
            "min_adx": 18.0,
            "stop_loss_pct": 0.10,
            "take_profit_pct": 0.35,
            **(parameters or {}),
        }
        super().__init__(
            name="TrendRegimeFilter",
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
        min_adx: float = float(self.parameters["min_adx"])
        stop_loss_pct: float = float(self.parameters["stop_loss_pct"])
        take_profit_pct: float = float(self.parameters["take_profit_pct"])

        # Determine macro regime from benchmark or snapshot features
        btc_feat = universe_snapshot.get(benchmark_id, {})
        regime = btc_feat.get("regime")
        btc_ema50_ratio = btc_feat.get("ema50_ratio", 1.0) or 1.0

        # Risk-off trigger: explicit RISK_OFF regime or BTC below 50 EMA by > 2%
        is_risk_off = (regime == "RISK_OFF") or (btc_ema50_ratio < 0.98)

        if is_risk_off:
            # Liquidate all open positions to cash
            for asset_id in current_positions.keys():
                signals.append(
                    StrategySignal(
                        asset_id=asset_id,
                        action=SignalAction.SELL,
                        target_weight=0.0,
                        reason="Macro Regime RISK_OFF: de-risking portfolio to cash preserve capital",
                    )
                )
            return signals

        # In RISK_ON / NEUTRAL regime: select assets in verified uptrends
        candidates: list[tuple[str, float]] = []
        for asset_id, feat in universe_snapshot.items():
            ema20_ratio = feat.get("ema20_ratio", 1.0) or 1.0
            ema50_ratio = feat.get("ema50_ratio", 1.0) or 1.0
            adx = feat.get("adx_14", 25.0) or 25.0
            ret_30d = feat.get("return_30d", 0.0) or 0.0

            # Price must be above EMA20 and EMA50 with trending ADX
            if ema20_ratio >= 1.0 and ema50_ratio >= 1.0 and adx >= min_adx:
                trend_score = (ema20_ratio - 1.0) + (ema50_ratio - 1.0) + (ret_30d * 0.5)
                candidates.append((asset_id, trend_score))

        candidates.sort(key=lambda x: x[1], reverse=True)
        top_selected_ids = {asset_id for asset_id, _ in candidates[:top_n]}

        target_weight = 1.0 / top_n if top_n > 0 else 0.0

        # Exit positions that dropped out of trend criteria
        for held_asset_id in list(current_positions.keys()):
            if held_asset_id not in top_selected_ids:
                signals.append(
                    StrategySignal(
                        asset_id=held_asset_id,
                        action=SignalAction.SELL,
                        target_weight=0.0,
                        reason="Trend degradation: asset failed EMA alignment or dropped out of top rank",
                    )
                )

        # Allocate to trending candidates
        for asset_id in top_selected_ids:
            signals.append(
                StrategySignal(
                    asset_id=asset_id,
                    action=SignalAction.BUY if asset_id not in current_positions else SignalAction.REBALANCE,
                    target_weight=target_weight,
                    stop_loss_pct=stop_loss_pct,
                    take_profit_pct=take_profit_pct,
                    reason=f"Verified uptrend in RISK_ON regime (target_weight={round(target_weight * 100, 1)}%)",
                )
            )

        return signals
