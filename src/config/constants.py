"""System-wide enumeration types and quantitative constants — v2.0.0."""

from enum import StrEnum


class AssetClass(StrEnum):
    CORE = "CORE"
    LARGE_CAP_ALT = "LARGE_CAP_ALT"
    ALTCOIN = "ALTCOIN"
    MID_CAP = "MID_CAP"
    SMALL_CAP = "SMALL_CAP"
    MEME = "MEME"
    UNKNOWN = "UNKNOWN"


class MarketRegime(StrEnum):
    RISK_ON = "RISK_ON"
    NEUTRAL = "NEUTRAL"
    RISK_OFF = "RISK_OFF"


class DataQualityStatus(StrEnum):
    GOOD = "GOOD"
    WARNING = "WARNING"
    INVALID = "INVALID"
    QUARANTINED = "QUARANTINED"   # preserved for audit, excluded from calculations
    STALE = "STALE"               # too old to use for live decisions
    UNAVAILABLE = "UNAVAILABLE"   # source did not return data


class DataMode(StrEnum):
    """Identifies the data source for any response.

    v2.0 rule: every API response, feature record, score, and backtest result
    must carry a DataMode value. The UI must display it explicitly.
    """
    LIVE = "LIVE"
    HISTORICAL = "HISTORICAL"
    SYNTHETIC_TEST = "SYNTHETIC_TEST"
    REPLAY = "REPLAY"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class Timeframe(StrEnum):
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class RiskFlag(StrEnum):
    VERY_NEW = "VERY_NEW"
    LOW_LIQUIDITY = "LOW_LIQUIDITY"
    HIGH_CONCENTRATION = "HIGH_CONCENTRATION"
    LIQUIDITY_REMOVAL = "LIQUIDITY_REMOVAL"
    ABNORMAL_VOLUME = "ABNORMAL_VOLUME"
    EXTREME_VOLATILITY = "EXTREME_VOLATILITY"
    SUPPLY_RISK = "SUPPLY_RISK"
    CONTRACT_RISK = "CONTRACT_RISK"
    UPCOMING_UNLOCK_48H = "UPCOMING_UNLOCK_48H"
    STALE_MARKET_DATA = "STALE_MARKET_DATA"


class RiskRejectionCode(StrEnum):
    """Machine-readable codes returned by RiskEngine when an order is rejected."""
    MAX_POSITION_SIZE_EXCEEDED = "MAX_POSITION_SIZE_EXCEEDED"
    INSUFFICIENT_CASH = "INSUFFICIENT_CASH"
    MAX_DAILY_LOSS_EXCEEDED = "MAX_DAILY_LOSS_EXCEEDED"
    MAX_EXPOSURE_EXCEEDED = "MAX_EXPOSURE_EXCEEDED"
    MAX_DRAWDOWN_EXCEEDED = "MAX_DRAWDOWN_EXCEEDED"
    ASSET_NOT_TRADABLE = "ASSET_NOT_TRADABLE"
    STALE_MARKET_DATA = "STALE_MARKET_DATA"
    PRICE_UNAVAILABLE = "PRICE_UNAVAILABLE"
    INSUFFICIENT_LIQUIDITY = "INSUFFICIENT_LIQUIDITY"
    MAX_MEME_EXPOSURE_EXCEEDED = "MAX_MEME_EXPOSURE_EXCEEDED"
    MAX_SECTOR_EXPOSURE_EXCEEDED = "MAX_SECTOR_EXPOSURE_EXCEEDED"
    MAX_OPEN_POSITIONS_EXCEEDED = "MAX_OPEN_POSITIONS_EXCEEDED"
    DUPLICATE_ORDER = "DUPLICATE_ORDER"
    LIVE_TRADING_DISABLED = "LIVE_TRADING_DISABLED"


class LedgerEventType(StrEnum):
    """Authoritative event types for the paper trading ledger."""
    ACCOUNT_CREATED = "ACCOUNT_CREATED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_ACCEPTED = "ORDER_ACCEPTED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_FILLED = "ORDER_FILLED"
    PARTIAL_FILL = "PARTIAL_FILL"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_UPDATED = "POSITION_UPDATED"
    POSITION_CLOSED = "POSITION_CLOSED"
    FEE_CHARGED = "FEE_CHARGED"
    MARK_TO_MARKET = "MARK_TO_MARKET"


class AlertCategory(StrEnum):
    """Separates trading signals from operational alerts and test alerts."""
    TRADING_SIGNAL = "TRADING_SIGNAL"
    OPERATIONAL = "OPERATIONAL"
    TEST_ALERT = "TEST_ALERT"


class HealthStatus(StrEnum):
    UP = "UP"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    DOWN = "DOWN"


class ListingStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DELISTED = "DELISTED"
    SUSPENDED = "SUSPENDED"
    UNKNOWN = "UNKNOWN"


# Timeframe in minutes mapping
TIMEFRAME_MINUTES = {
    Timeframe.M5: 5,
    Timeframe.M15: 15,
    Timeframe.H1: 60,
    Timeframe.H4: 240,
    Timeframe.D1: 1440,
}

# Default test universe — NOT for production scanner use
DEFAULT_TEST_UNIVERSE = ["BTC", "ETH", "SOL", "BNB", "NEAR", "RENDER", "DOGE", "PEPE"]
