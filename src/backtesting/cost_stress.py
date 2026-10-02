"""Cost stress testing helper for quantitative strategy sensitivity to transaction costs."""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from src.backtesting.engine import BacktestEngine
from src.utils.logging import get_logger

logger = get_logger("cost_stress")


@dataclass
class CostStressScenario:
    """Performance and attribution metrics for a specific cost stress scenario."""

    multiplier: float
    total_return_pct: float
    cagr: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    total_fees_usd: float
    total_slippage_usd: float
    net_pnl_usd: float
    trades_count: int
    win_rate: float

    def to_dict(self) -> dict[str, Any]:
        """Convert scenario to dictionary row for table rendering."""
        return asdict(self)


def run_cost_stress_test(
    engine: BacktestEngine,
    historical_candles: dict[str, list[dict[str, Any]]],
    historical_features: dict[str, list[dict[str, Any]]] | None = None,
    delisted_dates: dict[str, datetime] | None = None,
    multipliers: Sequence[float] = (1.0, 2.0, 3.0),
) -> list[CostStressScenario]:
    """Execute backtest across multiple fee and slippage stress multipliers (e.g. 1x, 2x, 3x).

    Args:
        engine: Baseline BacktestEngine configured with strategy and base friction.
        historical_candles: Market candle dictionary.
        historical_features: Optional feature dictionary.
        delisted_dates: Optional delisting timestamps dictionary.
        multipliers: Sequence of cost friction multipliers (default: 1.0, 2.0, 3.0).

    Returns:
        List of CostStressScenario instances representing the stress table.
    """
    scenarios: list[CostStressScenario] = []
    base_config = engine.config

    for mult in multipliers:
        logger.info("Executing cost stress scenario", multiplier=mult, strategy=base_config.strategy_name)
        stressed_config = base_config.model_copy(
            update={
                "maker_fee_bps": base_config.maker_fee_bps * mult,
                "taker_fee_bps": base_config.taker_fee_bps * mult,
                "fixed_slippage_bps": base_config.fixed_slippage_bps * mult,
                "impact_gamma": base_config.impact_gamma * mult,
            }
        )

        stressed_engine = BacktestEngine(stressed_config, engine.strategy)
        res = stressed_engine.run(
            historical_candles=historical_candles,
            historical_features=historical_features,
            delisted_dates=delisted_dates,
        )

        m = res.metrics
        scenario = CostStressScenario(
            multiplier=float(mult),
            total_return_pct=float(m.get("total_return_pct", 0.0)),
            cagr=float(m.get("cagr", 0.0)),
            sharpe_ratio=float(m.get("sharpe_ratio", 0.0)),
            sortino_ratio=float(m.get("sortino_ratio", 0.0)),
            max_drawdown_pct=float(m.get("max_drawdown_pct", 0.0)),
            total_fees_usd=float(m.get("total_fees_usd", 0.0)),
            total_slippage_usd=float(m.get("total_slippage_usd", 0.0)),
            net_pnl_usd=float(m.get("total_pnl_usd", 0.0)),
            trades_count=int(res.total_trades),
            win_rate=float(m.get("win_rate", 0.0)),
        )
        scenarios.append(scenario)

    return scenarios
