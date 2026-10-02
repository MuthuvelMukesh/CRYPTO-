"""Market data time-series models for OHLCV, orderbook, derivatives, on-chain, and tokenomics."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base
from src.utils.time import utc_now


class OHLCV(Base):
    """Historical Candlestick records."""

    __tablename__ = "ohlcv"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    market_id: Mapped[str] = mapped_column(String(64), ForeignKey("markets.id"), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True)  # '5m', '1h', '1d'

    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    quote_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(16), default="GOOD")
    data_mode: Mapped[str] = mapped_column(String(24), nullable=False, default="LIVE")

    __table_args__ = (
        Index("idx_ohlcv_query", "market_id", "timeframe", "time"),
    )


class ExchangeFailover(Base):
    """Log of multi-exchange failover events — v3.0."""

    __tablename__ = "exchange_failovers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    from_exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    to_exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)  # RATE_LIMIT_429, CONSECUTIVE_FAILURES, etc.
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)



class Trade(Base):
    """Public trade tick data."""

    __tablename__ = "trades"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    market_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trade_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    side: Mapped[str] = mapped_column(String(8), nullable=False)  # BUY / SELL
    price: Mapped[float] = mapped_column(Float, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)


class OrderbookSnapshot(Base):
    """L2 Top-of-book depth and spread snapshots."""

    __tablename__ = "orderbook_snapshots"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    market_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    bid_price: Mapped[float] = mapped_column(Float, nullable=False)
    bid_qty: Mapped[float] = mapped_column(Float, nullable=False)
    ask_price: Mapped[float] = mapped_column(Float, nullable=False)
    ask_qty: Mapped[float] = mapped_column(Float, nullable=False)
    spread_bps: Mapped[float] = mapped_column(Float, nullable=False)
    depth_2pct_bid_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    depth_2pct_ask_usd: Mapped[float | None] = mapped_column(Float, nullable=True)


class FundingRate(Base):
    """Perpetual futures funding rates."""

    __tablename__ = "funding_rates"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    market_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rate: Mapped[float] = mapped_column(Float, nullable=False)


class OpenInterest(Base):
    """Derivative open interest."""

    __tablename__ = "open_interest"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    market_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    open_interest: Mapped[float] = mapped_column(Float, nullable=False)
    open_interest_usd: Mapped[float | None] = mapped_column(Float, nullable=True)


class Liquidation(Base):
    """Exchange liquidations."""

    __tablename__ = "liquidations"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    market_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    long_liq_usd: Mapped[float] = mapped_column(Float, default=0.0)
    short_liq_usd: Mapped[float] = mapped_column(Float, default=0.0)


class MarketMetric(Base):
    """Aggregate macro market regime metrics."""

    __tablename__ = "market_metrics"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    total_market_cap_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    btc_dominance: Mapped[float | None] = mapped_column(Float, nullable=True)
    eth_dominance: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_24h_volume_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    regime: Mapped[str] = mapped_column(String(16), default="NEUTRAL")


class OnchainMetric(Base):
    """Protocol on-chain fundamentals."""

    __tablename__ = "onchain_metrics"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(32), ForeignKey("assets.id"), primary_key=True)
    tvl_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    tvl_change_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    fees_24h_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_24h_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    active_addresses_24h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tx_count_24h: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Tokenomics(Base):
    """Token supply, unlocks, and FDV metrics."""

    __tablename__ = "tokenomics"

    asset_id: Mapped[str] = mapped_column(String(32), ForeignKey("assets.id"), primary_key=True)
    circulating_supply: Mapped[float] = mapped_column(Float, nullable=False)
    total_supply: Mapped[float] = mapped_column(Float, nullable=False)
    max_supply: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap_usd: Mapped[float] = mapped_column(Float, nullable=False)
    fdv_usd: Mapped[float] = mapped_column(Float, nullable=False)
    fdv_to_market_cap_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    next_unlock_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_unlock_pct_of_circ: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class HolderMetric(Base):
    """Holder concentration and distribution (specialized for Meme & Small-Cap)."""

    __tablename__ = "holder_metrics"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(32), ForeignKey("assets.id"), primary_key=True)
    holder_count: Mapped[int] = mapped_column(Integer, nullable=False)
    holder_growth_24h_pct: Mapped[float] = mapped_column(Float, default=0.0)
    top_10_holders_pct: Mapped[float] = mapped_column(Float, default=0.0)
    whale_tx_count_24h: Mapped[int] = mapped_column(Integer, default=0)


class SocialMetric(Base):
    """Social sentiment and developer engagement."""

    __tablename__ = "social_metrics"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(32), ForeignKey("assets.id"), primary_key=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    social_volume_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    developer_commits_30d: Mapped[int | None] = mapped_column(Integer, nullable=True)
