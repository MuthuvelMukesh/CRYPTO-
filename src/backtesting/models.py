"""Data models and schemas for the quantitative backtesting engine."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.utils.time import utc_now


class OrderSide(StrEnum):
    """Order transaction side."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    """Order execution classification."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


class PositionSide(StrEnum):
    """Active position direction."""

    LONG = "LONG"
    FLAT = "FLAT"


class SignalAction(StrEnum):
    """Strategy signal action."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    REBALANCE = "REBALANCE"


class SlippageModelType(StrEnum):
    """Slippage modeling algorithms."""

    NONE = "none"
    FIXED_BPS = "fixed_bps"
    MARKET_IMPACT = "market_impact"


@dataclass
class StrategySignal:
    """Quantitative signal emitted by a strategy for an individual asset."""

    asset_id: str
    action: SignalAction
    target_weight: float = 0.0  # Fraction of portfolio equity (0.0 to 1.0)
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestTradeRecord:
    """Individual trade closed during backtest simulation."""

    trade_id: str
    asset_id: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    pnl_usd: float
    pnl_pct: float
    fees_usd: float = 0.0
    slippage_usd: float = 0.0
    exit_reason: str = "SIGNAL"
    low_confidence: bool = False
    low_confidence_reason: str | None = None


@dataclass
class EquityPoint:
    """Point-in-time portfolio mark-to-market snapshot."""

    time: datetime
    equity: float
    cash: float
    positions_value: float
    drawdown_pct: float
    benchmark_equity: float


class BacktestConfig(BaseModel):
    """Configuration parameters for a backtest simulation run."""

    model_config = ConfigDict(protected_namespaces=())

    strategy_name: str = Field(..., description="Unique name of strategy to execute")
    strategy_version: str = Field(default="1.0.0", description="Version of the strategy")
    start_date: datetime = Field(..., description="UTC start date for backtest")
    end_date: datetime = Field(..., description="UTC end date for backtest")
    initial_capital: float = Field(default=100000.0, ge=1000.0, description="Starting cash in USD")
    maker_fee_bps: float = Field(default=2.0, ge=0.0, description="Maker fee in basis points (0.02% default)")
    taker_fee_bps: float = Field(default=5.0, ge=0.0, description="Taker fee in basis points (0.05% default)")
    slippage_model: SlippageModelType = Field(default=SlippageModelType.MARKET_IMPACT, description="Slippage model")
    fixed_slippage_bps: float = Field(default=5.0, ge=0.0, description="Fixed slippage in basis points")
    impact_gamma: float = Field(default=0.1, ge=0.0, description="Square-root market impact parameter gamma")
    benchmark_symbol: str = Field(default="BTC", description="Benchmark symbol for comparative performance")
    max_open_positions: int = Field(default=10, ge=1, le=50, description="Maximum concurrent active positions")
    max_position_weight: float = Field(default=0.25, ge=0.01, le=1.0, description="Max equity fraction per asset")
    cash_buffer_pct: float = Field(default=0.02, ge=0.0, le=0.5, description="Min cash reserve fraction")
    timeframe: str = Field(default="1d", description="Bar timeframe (e.g. 1h, 1d, 4h)")
    intrabar_order: str = Field(default="stop_first", description="Bracket trigger priority: 'stop_first' or 'tp_first'")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Strategy-specific hyperparameters")


class BacktestResult(BaseModel):
    """Complete summary results of an executed backtest."""

    model_config = ConfigDict(protected_namespaces=())

    id: str = Field(..., description="Unique backtest execution UUID")
    config: BacktestConfig
    metrics: dict[str, Any] = Field(..., description="Calculated statistical and financial metrics")
    total_trades: int = Field(default=0)
    trades: list[dict[str, Any]] = Field(default_factory=list, description="List of trade logs")
    equity_curve: list[dict[str, Any]] = Field(default_factory=list, description="Time series of equity values")
    created_at: datetime = Field(default_factory=utc_now)
