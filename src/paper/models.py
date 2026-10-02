"""Data transfer schemas and Pydantic models for virtual paper brokerage."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.utils.time import utc_now


class PaperOrderSide(StrEnum):
    """Paper order transaction direction."""

    BUY = "BUY"
    SELL = "SELL"


class PaperOrderType(StrEnum):
    """Paper order execution type."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"


class PaperOrderStatus(StrEnum):
    """Order lifecycle status."""

    PENDING = "PENDING"
    OPEN = "OPEN"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class OrderSubmitRequest(BaseModel):
    """Payload to place a virtual paper order — v2.0.

    idempotency_key: optional client-generated UUID to prevent duplicate submission.
    If an order with this key already exists, DuplicateOrderError is raised.
    """

    model_config = ConfigDict(protected_namespaces=())

    account_id: str = Field(default="default_paper", description="Virtual account identifier")
    symbol: str = Field(..., description="Asset symbol to trade (e.g. BTC, ETH, SOL, DOGE)")
    side: PaperOrderSide = Field(..., description="BUY or SELL")
    order_type: PaperOrderType = Field(default=PaperOrderType.MARKET, description="Order execution type")
    quantity: float = Field(..., gt=0.0, description="Order asset quantity")
    limit_price: float | None = Field(default=None, gt=0.0, description="Optional limit price")
    stop_price: float | None = Field(default=None, gt=0.0, description="Optional stop trigger price")
    # v2.0: idempotency key — client must supply a unique UUID per distinct order intention
    idempotency_key: str | None = Field(
        default=None,
        description="Client-generated UUID to prevent duplicate order submission",
    )


class FillResponse(BaseModel):
    """Execution fill details."""

    id: str
    order_id: str
    time: str
    fill_price: float
    quantity: float
    fee_usd: float
    slippage_usd: float


class OrderResponse(BaseModel):
    """Order status and confirmation."""

    model_config = ConfigDict(protected_namespaces=())

    id: str
    account_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    status: str
    fills: list[FillResponse] = Field(default_factory=list)
    created_at: str


class PositionResponse(BaseModel):
    """Open or closed virtual paper position — v2.0.

    price_stale: True if the current_price used for MTM is stale (no live data).
    When True, unrealized_pnl and market_value should be treated as approximate.
    """

    id: str
    account_id: str
    symbol: str
    side: str
    quantity: float
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    realized_pnl: float
    entry_time: str
    exit_time: str | None = None
    is_open: bool
    exit_reason: str | None = None
    # v2.0: explicit staleness flag — never silently use stale prices
    price_stale: bool = False


class PortfolioSummaryResponse(BaseModel):
    """Comprehensive real-time paper account state and risk metrics."""

    account_id: str
    name: str
    base_currency: str
    starting_balance: float
    cash_balance: float
    invested_capital: float
    total_equity: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    total_return_pct: float
    drawdown_pct: float
    peak_equity: float
    gross_exposure: float
    net_exposure: float
    meme_exposure_pct: float
    max_single_position_pct: float
    open_positions_count: int
    open_positions: list[PositionResponse] = Field(default_factory=list)
    updated_at: str = Field(default_factory=lambda: utc_now().isoformat())


class RiskValidationResult(BaseModel):
    """Risk engine inspection outcome for order submission."""

    passed: bool
    reason: str = ""
    violations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
