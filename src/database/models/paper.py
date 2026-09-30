"""Paper trading models for virtual accounts, orders, fills, positions, and equity curve."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base
from src.utils.time import utc_now


class PaperAccount(Base):
    """Virtual paper-trading brokerage account."""

    __tablename__ = "paper_accounts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(16), default="USD")
    starting_balance: Mapped[float] = mapped_column(Float, default=100000.0)
    cash_balance: Mapped[float] = mapped_column(Float, default=100000.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    orders: Mapped[list["PaperOrder"]] = relationship("PaperOrder", back_populates="account")
    positions: Mapped[list["PaperPosition"]] = relationship("PaperPosition", back_populates="account")


class PaperOrder(Base):
    """Simulated order lifecycle records — v2.0.

    idempotency_key: client-supplied key to prevent duplicate submissions.
    exchange_id: always 'paper_simulated' in v2.0 (never a real exchange ID).
    """

    __tablename__ = "paper_orders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(32), ForeignKey("paper_accounts.id"), nullable=False)
    asset_id: Mapped[str] = mapped_column(String(32), ForeignKey("assets.id"), nullable=False)
    exchange_id: Mapped[str] = mapped_column(String(32), nullable=False, default="paper_simulated")
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)  # MARKET, LIMIT, STOP_LOSS
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # BUY, SELL
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    limit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="PENDING")
    # v2.0: idempotency_key prevents duplicate order submission
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    account: Mapped["PaperAccount"] = relationship("PaperAccount", back_populates="orders")
    fills: Mapped[list["PaperFill"]] = relationship("PaperFill", back_populates="order")


class PaperFill(Base):
    """Execution fill details."""

    __tablename__ = "paper_fills"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), ForeignKey("paper_orders.id"), nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    fill_price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    fee_usd: Mapped[float] = mapped_column(Float, default=0.0)
    slippage_usd: Mapped[float] = mapped_column(Float, default=0.0)

    order: Mapped["PaperOrder"] = relationship("PaperOrder", back_populates="fills")


class PaperPosition(Base):
    """Open and closed paper trading positions."""

    __tablename__ = "paper_positions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(32), ForeignKey("paper_accounts.id"), nullable=False)
    asset_id: Mapped[str] = mapped_column(String(32), ForeignKey("assets.id"), nullable=False)
    side: Mapped[str] = mapped_column(String(8), default="LONG")
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    avg_entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    exit_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)

    account: Mapped["PaperAccount"] = relationship("PaperAccount", back_populates="positions")


class PaperEquity(Base):
    """Time-series equity curve of paper trading accounts."""

    __tablename__ = "paper_equity"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(32), ForeignKey("paper_accounts.id"), primary_key=True)

    equity: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    invested_capital: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)


class PortfolioSnapshot(Base):
    """Point-in-time risk and exposure ledger."""

    __tablename__ = "portfolio_snapshots"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(32), ForeignKey("paper_accounts.id"), primary_key=True)

    gross_exposure: Mapped[float] = mapped_column(Float, nullable=False)
    net_exposure: Mapped[float] = mapped_column(Float, nullable=False)
    meme_exposure_pct: Mapped[float] = mapped_column(Float, default=0.0)
    max_single_position_pct: Mapped[float] = mapped_column(Float, default=0.0)
    positions_count: Mapped[int] = mapped_column(Integer, default=0)
