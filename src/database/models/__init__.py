"""Database models namespace package."""

from src.database.models.alert import Alert, SystemEvent
from src.database.models.asset import Asset, AssetCategory, Exchange, Market
from src.database.models.backtest import Backtest, BacktestTrade
from src.database.models.base import Base, TimestampMixin
from src.database.models.features import Feature
from src.database.models.market_data import (
    OHLCV,
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
from src.database.models.scoring import Score, Signal

__all__ = [
    "Alert",
    "Asset",
    "AssetCategory",
    "Backtest",
    "BacktestTrade",
    "Base",
    "Exchange",
    "Feature",
    "FundingRate",
    "HolderMetric",
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
    "Score",
    "Signal",
    "SocialMetric",
    "SystemEvent",
    "TimestampMixin",
    "Tokenomics",
    "Trade",
]
