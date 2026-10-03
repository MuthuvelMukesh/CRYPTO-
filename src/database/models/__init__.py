"""Database models namespace package — v2.0."""

from src.database.models.alert import Alert, SystemEvent
from src.database.models.asset import Asset, AssetCategory, Exchange, Market
from src.database.models.backtest import Backtest, BacktestTrade
from src.database.models.base import Base, TimestampMixin
from src.database.models.features import Feature
from src.database.models.ledger import LedgerEvent
from src.database.models.market_data import (
    OHLCV,
    ExchangeFailover,
    FundingRate,
    HolderMetric,
    Liquidation,
    MarketMetric,
    OnchainMetric,
    OpenInterest,
    OrderbookSnapshot,
    SocialMetric,
    Tokenomics,
    Trade,
)
from src.database.models.paper import (
    PaperAccount,
    PaperEquity,
    PaperFill,
    PaperOrder,
    PaperPosition,
    PortfolioSnapshot,
)
from src.database.models.scanner import ScannerSnapshot, UniverseSnapshot
from src.database.models.scoring import Score, Signal
from src.database.models.watchlist import WatchlistItem

__all__ = [
    "Alert",
    "Asset",
    "AssetCategory",
    "Backtest",
    "BacktestTrade",
    "Base",
    "Exchange",
    "ExchangeFailover",
    "Feature",
    "FundingRate",
    "HolderMetric",
    "LedgerEvent",
    "Liquidation",
    "Market",
    "MarketMetric",
    "OHLCV",
    "OnchainMetric",
    "OpenInterest",
    "OrderbookSnapshot",
    "PaperAccount",
    "PaperEquity",
    "PaperFill",
    "PaperOrder",
    "PaperPosition",
    "PortfolioSnapshot",
    "ScannerSnapshot",
    "Score",
    "Signal",
    "SocialMetric",
    "SystemEvent",
    "TimestampMixin",
    "Tokenomics",
    "Trade",
    "UniverseSnapshot",
]
