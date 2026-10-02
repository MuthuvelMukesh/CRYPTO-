"""Core event-driven bar-by-bar backtesting simulation engine with point-in-time universe support."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.backtesting.execution import ExecutionSimulator
from src.backtesting.metrics import compute_complete_metrics
from src.backtesting.models import (
    BacktestConfig,
    BacktestResult,
    BacktestTradeRecord,
    EquityPoint,
    OrderSide,
    SignalAction,
    StrategySignal,
)
from src.backtesting.strategies.base import BaseStrategy
from src.database.models.backtest import Backtest as BacktestModel
from src.database.models.backtest import BacktestTrade as BacktestTradeModel
from src.utils.logging import get_logger
from src.utils.time import utc_now

logger = get_logger("backtest_engine")


class BacktestEngine:
    """Quantitative backtest simulation engine executing event-driven bar simulation."""

    def __init__(self, config: BacktestConfig, strategy: BaseStrategy) -> None:
        self.config = config
        self.strategy = strategy
        self.simulator = ExecutionSimulator(
            maker_fee_bps=config.maker_fee_bps,
            taker_fee_bps=config.taker_fee_bps,
            slippage_model=config.slippage_model,
            fixed_slippage_bps=config.fixed_slippage_bps,
            impact_gamma=config.impact_gamma,
        )

    def run(
        self,
        historical_candles: dict[str, list[dict[str, Any]]],
        historical_features: dict[str, list[dict[str, Any]]] | None = None,
        delisted_dates: dict[str, datetime] | None = None,
    ) -> BacktestResult:
        """Execute the backtesting simulation on provided chronological candle and feature data.

        Args:
            historical_candles: Mapping of symbol/asset_id to chronological list of candle dicts:
                                [{'time': datetime, 'open': float, 'high': float, 'low': float,
                                  'close': float, 'volume': float, 'volume_usd': float}, ...]
            historical_features: Optional mapping of symbol/asset_id to chronological list of feature dicts
                                matching timestamps in candles.
            delisted_dates: Optional mapping of symbol/asset_id to UTC delisting datetime. Coins are strictly
                            liquidated and removed from universe once time >= delisting date (survivorship bias prevention).

        Returns:
            BacktestResult with complete trade journal, equity curve, and metrics.
        """
        backtest_id = str(uuid.uuid4())
        logger.info(
            "Starting backtest simulation",
            backtest_id=backtest_id,
            strategy=self.strategy.name,
            initial_capital=self.config.initial_capital,
        )

        delisted_dates = delisted_dates or {}

        # 1. Aggregate, pre-index, and sort all distinct chronological timestamps
        all_timestamps: set[datetime] = set()
        candle_lookup: dict[tuple[str, datetime], dict[str, Any]] = {}
        candles_by_time: dict[datetime, dict[str, dict[str, Any]]] = {}
        for asset_id, candle_list in historical_candles.items():
            for c_init in candle_list:
                t = c_init["time"]
                all_timestamps.add(t)
                candle_lookup[(asset_id, t)] = c_init
                if t not in candles_by_time:
                    candles_by_time[t] = {}
                candles_by_time[t][asset_id] = c_init

        feature_lookup: dict[tuple[str, datetime], dict[str, Any]] = {}
        if historical_features:
            for asset_id, feat_list in historical_features.items():
                for f in feat_list:
                    feature_lookup[(asset_id, f["time"])] = f

        timeline: list[datetime] = sorted(all_timestamps)
        # Filter timeline within config bounds
        timeline = [t for t in timeline if self.config.start_date <= t <= self.config.end_date]

        if not timeline:
            raise ValueError(
                f"No candle data found within range {self.config.start_date} to {self.config.end_date}"
            )

        # 2. Benchmark initial price tracking
        benchmark_id = self.config.benchmark_symbol
        benchmark_initial_price: float | None = None
        for t in timeline:
            c_bm = candle_lookup.get((benchmark_id, t))
            if c_bm and c_bm.get("close", 0) > 0:
                benchmark_initial_price = float(c_bm["close"])
                break

        # State tracking
        cash = float(self.config.initial_capital)
        current_equity = cash
        positions: dict[str, dict[str, Any]] = {}
        closed_trades: list[BacktestTradeRecord] = []
        equity_curve: list[EquityPoint] = []
        peak_equity = float(self.config.initial_capital)
        pending_signals: list[StrategySignal] = []

        # 3. Bar-by-Bar Event Loop
        for current_time in timeline:
            candles_at_t = candles_by_time.get(current_time, {})

            # Step A: Execute Pending Signals from bar t-1 at current bar open (Anti-lookahead protected)
            if pending_signals:
                # 1. Process pending SELL and EXIT signals first to free cash
                for sig in pending_signals:
                    if sig.action == SignalAction.SELL and sig.asset_id in positions:
                        c_sell = candles_at_t.get(sig.asset_id)
                        pos = positions[sig.asset_id]
                        sell_low_conf: bool = False
                        sell_low_reason: str | None = None
                        if not c_sell or float(c_sell.get("open", 0)) <= 0:
                            exit_price = pos["entry_price"]
                            vol_usd = 0.0
                            sell_low_conf = True
                            sell_low_reason = "Missing candle open price at queued signal exit"
                        else:
                            exit_price = float(c_sell["open"])
                            vol_usd, sell_low_conf, sell_low_reason = self._resolve_candle_volume(c_sell)

                        spread_bps = self._estimate_spread(sig.asset_id, current_time, feature_lookup)
                        trade = self._close_position(
                            positions=positions,
                            asset_id=sig.asset_id,
                            exit_price=exit_price,
                            exit_time=current_time,
                            exit_reason=sig.reason or "SIGNAL",
                            volume_24h_usd=vol_usd,
                            spread_bps=spread_bps,
                            low_confidence=sell_low_conf or pos.get("low_confidence", False),
                            low_confidence_reason=sell_low_reason or pos.get("low_confidence_reason"),
                        )
                        cash += (trade.exit_price * trade.quantity) - trade.fees_usd
                        closed_trades.append(trade)

                # 2. Process pending BUY and REBALANCE signals at current bar open
                available_investable_cash = max(0.0, cash - (current_equity * self.config.cash_buffer_pct))
                buy_signals = [s for s in pending_signals if s.action in (SignalAction.BUY, SignalAction.REBALANCE)]

                for sig in buy_signals:
                    delist_time = delisted_dates.get(sig.asset_id)
                    if delist_time and current_time >= delist_time:
                        continue  # Do not execute buys on delisted assets

                    if len(positions) >= self.config.max_open_positions and sig.asset_id not in positions:
                        continue

                    c_buy = candles_at_t.get(sig.asset_id)
                    if not c_buy or float(c_buy.get("open", 0)) <= 0:
                        continue

                    base_price = float(c_buy["open"])
                    vol_usd, buy_low_conf, buy_low_reason = self._resolve_candle_volume(c_buy)
                    spread_bps = self._estimate_spread(sig.asset_id, current_time, feature_lookup)

                    target_weight = min(sig.target_weight, self.config.max_position_weight)
                    target_value_usd = current_equity * target_weight

                    current_pos = positions.get(sig.asset_id)
                    current_val = (current_pos["quantity"] * base_price) if current_pos else 0.0
                    delta_val_usd = target_value_usd - current_val

                    if delta_val_usd > 10.0 and available_investable_cash >= delta_val_usd:
                        fill_price, _, slippage_usd, fee_usd = self.simulator.calculate_fill(
                            side=OrderSide.BUY,
                            base_price=base_price,
                            order_value_usd=delta_val_usd,
                            volume_24h_usd=vol_usd,
                            spread_bps=spread_bps,
                            is_maker=False,
                        )
                        qty_to_buy = delta_val_usd / fill_price
                        total_outlay = (qty_to_buy * fill_price) + fee_usd

                        if cash >= total_outlay:
                            cash -= total_outlay
                            available_investable_cash = max(0.0, available_investable_cash - total_outlay)

                            if sig.asset_id in positions:
                                existing = positions[sig.asset_id]
                                new_qty = existing["quantity"] + qty_to_buy
                                new_entry = (
                                    (existing["quantity"] * existing["entry_price"]) + (qty_to_buy * fill_price)
                                ) / new_qty
                                existing["quantity"] = new_qty
                                existing["entry_price"] = new_entry
                                existing["accumulated_fees"] = existing.get("accumulated_fees", 0.0) + fee_usd
                                existing["accumulated_slippage"] = existing.get("accumulated_slippage", 0.0) + slippage_usd
                            else:
                                positions[sig.asset_id] = {
                                    "quantity": qty_to_buy,
                                    "entry_price": fill_price,
                                    "entry_time": current_time,
                                    "stop_loss_pct": sig.stop_loss_pct,
                                    "take_profit_pct": sig.take_profit_pct,
                                    "accumulated_fees": fee_usd,
                                    "accumulated_slippage": slippage_usd,
                                    "low_confidence": buy_low_conf,
                                    "low_confidence_reason": buy_low_reason,
                                }

                pending_signals = []

            # Step B: Check Bracket Orders (Stop Loss / Take Profit) on open positions
            for asset_id in list(positions.keys()):
                pos = positions[asset_id]
                c_bracket = candles_at_t.get(asset_id)
                if not c_bracket:
                    continue

                trigger = self.simulator.check_bracket_triggers(
                    entry_price=pos["entry_price"],
                    candle_high=float(c_bracket["high"]),
                    candle_low=float(c_bracket["low"]),
                    candle_open=float(c_bracket["open"]),
                    stop_loss_pct=pos.get("stop_loss_pct"),
                    take_profit_pct=pos.get("take_profit_pct"),
                    intrabar_order=self.config.intrabar_order,
                )

                if trigger:
                    reason, trigger_price = trigger
                    vol_usd, brk_low_conf, brk_low_reason = self._resolve_candle_volume(c_bracket)
                    spread_bps = self._estimate_spread(asset_id, current_time, feature_lookup)
                    trade = self._close_position(
                        positions=positions,
                        asset_id=asset_id,
                        exit_price=trigger_price,
                        exit_time=current_time,
                        exit_reason=reason,
                        volume_24h_usd=vol_usd,
                        spread_bps=spread_bps,
                        low_confidence=brk_low_conf or pos.get("low_confidence", False),
                        low_confidence_reason=brk_low_reason or pos.get("low_confidence_reason"),
                    )
                    cash += (trade.exit_price * trade.quantity) - trade.fees_usd
                    closed_trades.append(trade)

            # Step C: Survivorship check & Delisting liquidations
            for asset_id in list(positions.keys()):
                delist_time = delisted_dates.get(asset_id)
                if delist_time and current_time >= delist_time:
                    c_delist = candles_at_t.get(asset_id)
                    pos = positions[asset_id]
                    if c_delist and float(c_delist.get("close", 0)) > 0:
                        exit_price = float(c_delist["close"])
                        vol_usd, delist_low_conf, delist_low_reason = self._resolve_candle_volume(c_delist)
                    else:
                        exit_price = pos["entry_price"]
                        vol_usd = 0.0
                        delist_low_conf = True
                        delist_low_reason = "Liquidated at delisting with missing candle data"

                    spread_bps = self._estimate_spread(asset_id, current_time, feature_lookup)
                    trade = self._close_position(
                        positions=positions,
                        asset_id=asset_id,
                        exit_price=exit_price,
                        exit_time=current_time,
                        exit_reason="DELISTED",
                        volume_24h_usd=vol_usd,
                        spread_bps=spread_bps,
                        low_confidence=delist_low_conf or pos.get("low_confidence", False),
                        low_confidence_reason=delist_low_reason or pos.get("low_confidence_reason"),
                    )
                    cash += (trade.exit_price * trade.quantity) - trade.fees_usd
                    closed_trades.append(trade)

            # Step D: Mark current equity and construct positions summary at bar close
            positions_val = 0.0
            positions_summary: dict[str, dict[str, Any]] = {}
            for asset_id, pos in positions.items():
                c_mark = candles_at_t.get(asset_id)
                curr_price = float(c_mark["close"]) if c_mark and float(c_mark.get("close", 0)) > 0 else pos["entry_price"]
                pos_val = pos["quantity"] * curr_price
                positions_val += pos_val
                positions_summary[asset_id] = {
                    "quantity": pos["quantity"],
                    "entry_price": pos["entry_price"],
                    "current_price": curr_price,
                    "unrealized_pnl": pos_val - (pos["quantity"] * pos["entry_price"]),
                    "value": pos_val,
                }

            current_equity = cash + positions_val
            peak_equity = max(peak_equity, current_equity)
            drawdown_pct = ((current_equity - peak_equity) / peak_equity * 100.0) if peak_equity > 0 else 0.0

            # Benchmark equity mark
            bm_candle = candles_at_t.get(benchmark_id)
            if bm_candle and benchmark_initial_price and benchmark_initial_price > 0:
                bm_equity = float(self.config.initial_capital) * (
                    float(bm_candle["close"]) / benchmark_initial_price
                )
            else:
                bm_equity = float(self.config.initial_capital)

            equity_curve.append(
                EquityPoint(
                    time=current_time,
                    equity=round(current_equity, 2),
                    cash=round(cash, 2),
                    positions_value=round(positions_val, 2),
                    drawdown_pct=round(drawdown_pct, 2),
                    benchmark_equity=round(bm_equity, 2),
                )
            )

            # Step E: Construct point-in-time universe snapshot at bar close (O(assets) lookup)
            universe_snapshot: dict[str, dict[str, Any]] = {}
            for asset_id, c in candles_at_t.items():
                delist_time = delisted_dates.get(asset_id)
                if delist_time and current_time >= delist_time:
                    continue
                feat = feature_lookup.get((asset_id, current_time), {})
                universe_snapshot[asset_id] = {**c, **feat}

            # Step F: Strategy Signal Generation at bar close -> queued for fill at bar t+1 open
            signals = self.strategy.generate_signals(
                current_time=current_time,
                universe_snapshot=universe_snapshot,
                current_positions=positions_summary,
                cash=cash,
                total_equity=current_equity,
            )
            pending_signals = signals

        # 4. Simulation End: Liquidate any remaining open positions
        final_time = timeline[-1]
        candles_at_final = candles_by_time.get(final_time, {})
        for asset_id in list(positions.keys()):
            c_final = candles_at_final.get(asset_id)
            pos = positions[asset_id]
            if c_final and float(c_final.get("close", 0)) > 0:
                final_price = float(c_final["close"])
                vol_usd, fin_low_conf, fin_low_reason = self._resolve_candle_volume(c_final)
            else:
                final_price = pos["entry_price"]
                vol_usd = 0.0
                fin_low_conf = True
                fin_low_reason = "Liquidated at simulation end with missing candle data"

            spread_bps = self._estimate_spread(asset_id, final_time, feature_lookup)
            trade = self._close_position(
                positions=positions,
                asset_id=asset_id,
                exit_price=final_price,
                exit_time=final_time,
                exit_reason="BACKTEST_END",
                volume_24h_usd=vol_usd,
                spread_bps=spread_bps,
                low_confidence=fin_low_conf or pos.get("low_confidence", False),
                low_confidence_reason=fin_low_reason or pos.get("low_confidence_reason"),
            )
            cash += (trade.exit_price * trade.quantity) - trade.fees_usd
            closed_trades.append(trade)

        # 5. Compute full statistical metrics
        metrics = compute_complete_metrics(
            equity_curve=equity_curve,
            trades=closed_trades,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            timeframe=self.config.timeframe,
        )

        low_confidence_trades = [t for t in closed_trades if t.low_confidence]
        metrics["low_confidence_trades_count"] = len(low_confidence_trades)
        metrics["low_confidence_reasons"] = sorted(
            {t.low_confidence_reason for t in low_confidence_trades if t.low_confidence_reason}
        )

        result = BacktestResult(
            id=backtest_id,
            config=self.config,
            metrics=metrics,
            total_trades=len(closed_trades),
            trades=[self._serialize_trade(t) for t in closed_trades],
            equity_curve=[self._serialize_equity(e) for e in equity_curve],
            created_at=utc_now(),
        )

        logger.info(
            "Backtest simulation completed",
            backtest_id=backtest_id,
            total_return_pct=metrics.get("total_return_pct"),
            cagr=metrics.get("cagr"),
            sharpe_ratio=metrics.get("sharpe_ratio"),
            max_drawdown_pct=metrics.get("max_drawdown_pct"),
            trades_count=len(closed_trades),
        )
        return result

    def _estimate_spread(
        self,
        asset_id: str,
        current_time: datetime,
        feature_lookup: dict[tuple[str, datetime], dict[str, Any]],
    ) -> float:
        """Derive estimated spread in bps from features or volatility."""
        feat = feature_lookup.get((asset_id, current_time), {})
        return self.simulator.estimate_spread_bps(
            feature_spread_bps=feat.get("spread_est_bps"),
            atr_14_pct=feat.get("atr_14_pct"),
        )

    @staticmethod
    def _resolve_candle_volume(c: dict[str, Any] | None) -> tuple[float, bool, str | None]:
        """Extract 24h volume in USD without silent synthetic fallbacks.

        Returns:
            Tuple of (volume_usd, is_low_confidence, reason_if_low_confidence).
        """
        if not c:
            return 0.0, True, "Missing candle data for volume calculation"
        vol_usd = c.get("volume_usd")
        if vol_usd is not None and float(vol_usd) > 0:
            return float(vol_usd), False, None
        vol = c.get("volume")
        close = c.get("close")
        if vol is not None and close is not None and float(vol) > 0 and float(close) > 0:
            return float(vol) * float(close), False, None
        return 0.0, True, "Missing or non-positive volume_usd in candle"

    def _close_position(
        self,
        positions: dict[str, dict[str, Any]],
        asset_id: str,
        exit_price: float,
        exit_time: datetime,
        exit_reason: str,
        volume_24h_usd: float,
        spread_bps: float | None = None,
        low_confidence: bool = False,
        low_confidence_reason: str | None = None,
    ) -> BacktestTradeRecord:
        """Close an active position and generate trade record with friction attribution."""
        pos = positions.pop(asset_id)
        qty = pos["quantity"]
        entry_price = pos["entry_price"]
        entry_time = pos["entry_time"]

        fill_price, _, slippage_usd, fee_usd = self.simulator.calculate_fill(
            side=OrderSide.SELL,
            base_price=exit_price,
            order_value_usd=qty * exit_price,
            volume_24h_usd=volume_24h_usd,
            spread_bps=spread_bps,
            is_maker=False,
        )

        gross_pnl_usd = (fill_price - entry_price) * qty
        total_fees = pos.get("accumulated_fees", 0.0) + fee_usd
        total_slippage = pos.get("accumulated_slippage", 0.0) + slippage_usd
        net_pnl_usd = gross_pnl_usd - total_fees
        pnl_pct = (net_pnl_usd / (entry_price * qty)) * 100.0 if (entry_price * qty) > 0 else 0.0

        is_low_conf = low_confidence or pos.get("low_confidence", False)
        conf_reason = low_confidence_reason or pos.get("low_confidence_reason")

        return BacktestTradeRecord(
            trade_id=str(uuid.uuid4()),
            asset_id=asset_id,
            entry_time=entry_time,
            exit_time=exit_time,
            entry_price=round(entry_price, 4),
            exit_price=round(fill_price, 4),
            quantity=round(qty, 6),
            pnl_usd=round(net_pnl_usd, 2),
            pnl_pct=round(pnl_pct, 2),
            fees_usd=round(total_fees, 2),
            slippage_usd=round(total_slippage, 2),
            exit_reason=exit_reason,
            low_confidence=is_low_conf,
            low_confidence_reason=conf_reason,
        )

    @staticmethod
    def _serialize_trade(t: BacktestTradeRecord) -> dict[str, Any]:
        return {
            "trade_id": t.trade_id,
            "asset_id": t.asset_id,
            "entry_time": t.entry_time.isoformat(),
            "exit_time": t.exit_time.isoformat(),
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "quantity": t.quantity,
            "pnl_usd": t.pnl_usd,
            "pnl_pct": t.pnl_pct,
            "fees_usd": t.fees_usd,
            "slippage_usd": t.slippage_usd,
            "exit_reason": t.exit_reason,
            "low_confidence": t.low_confidence,
            "low_confidence_reason": t.low_confidence_reason,
        }

    @staticmethod
    def _serialize_equity(e: EquityPoint) -> dict[str, Any]:
        return {
            "time": e.time.isoformat(),
            "equity": e.equity,
            "cash": e.cash,
            "positions_value": e.positions_value,
            "drawdown_pct": e.drawdown_pct,
            "benchmark_equity": e.benchmark_equity,
        }

    @staticmethod
    async def persist_result(session: AsyncSession, result: BacktestResult) -> None:
        """Persist backtest run and executed trade logs into database tables."""
        m = result.metrics
        backtest_row = BacktestModel(
            id=result.id,
            strategy_name=result.config.strategy_name,
            strategy_version=result.config.strategy_version,
            start_time=result.config.start_date,
            end_time=result.config.end_date,
            parameters=result.config.parameters,
            total_return_pct=float(m.get("total_return_pct", 0.0)),
            cagr=float(m.get("cagr", 0.0)),
            sharpe_ratio=float(m.get("sharpe_ratio", 0.0)),
            sortino_ratio=float(m.get("sortino_ratio", 0.0)),
            max_drawdown_pct=float(m.get("max_drawdown_pct", 0.0)),
            win_rate=float(m.get("win_rate", 0.0)),
            profit_factor=float(m.get("profit_factor", 0.0)),
            benchmark_return_pct=float(m.get("benchmark_return_pct", 0.0)),
            created_at=result.created_at,
        )
        session.add(backtest_row)

        for t in result.trades:
            trade_row = BacktestTradeModel(
                id=t["trade_id"],
                backtest_id=result.id,
                asset_id=t["asset_id"],
                entry_time=datetime.fromisoformat(t["entry_time"]),
                exit_time=datetime.fromisoformat(t["exit_time"]),
                entry_price=float(t["entry_price"]),
                exit_price=float(t["exit_price"]),
                pnl_usd=float(t["pnl_usd"]),
                pnl_pct=float(t["pnl_pct"]),
                fees_usd=float(t.get("fees_usd", 0.0)),
                slippage_usd=float(t.get("slippage_usd", 0.0)),
                exit_reason=t["exit_reason"],
            )
            session.add(trade_row)

        await session.commit()
        logger.info("Persisted backtest run to database", backtest_id=result.id, trades_persisted=len(result.trades))
