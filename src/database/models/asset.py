"""Asset master, category, exchange, and market pair models."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base
from src.utils.time import utc_now


class Asset(Base):
    """Canonical cryptocurrency asset registry."""

    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # e.g., 'BTC'
    name: Mapped[str] = mapped_column(String(128), nullable=False)  # e.g., 'Bitcoin'
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    asset_class: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # CORE, ALTCOIN, MEME
    primary_sector: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # Layer 1, DeFi
    coingecko_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contract_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chain: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # Relationships
    markets: Mapped[list["Market"]] = relationship("Market", back_populates="asset")
    categories: Mapped[list["AssetCategory"]] = relationship("AssetCategory", back_populates="asset")


class AssetCategory(Base):
    """Many-to-many asset category categorization (e.g. DeFi, AI, Layer 1)."""

    __tablename__ = "asset_categories"

    asset_id: Mapped[str] = mapped_column(String(32), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    category: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)

    asset: Mapped["Asset"] = relationship("Asset", back_populates="categories")


class Exchange(Base):
    """Supported trading venue."""

    __tablename__ = "exchanges"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # e.g., 'binance'
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_dex: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    markets: Mapped[list["Market"]] = relationship("Market", back_populates="exchange")


class Market(Base):
    """Tradable trading pair on a specific exchange."""

    __tablename__ = "markets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g., 'binance:BTC/USDT'
    exchange_id: Mapped[str] = mapped_column(String(32), ForeignKey("exchanges.id"), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(String(32), ForeignKey("assets.id"), nullable=False, index=True)
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False)  # 'USDT'
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)  # 'BTC/USDT'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    asset: Mapped["Asset"] = relationship("Asset", back_populates="markets")
    exchange: Mapped["Exchange"] = relationship("Exchange", back_populates="markets")
