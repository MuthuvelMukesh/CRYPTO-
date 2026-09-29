"""System-wide enumeration types and quantitative constants."""

from enum import StrEnum


class AssetClass(StrEnum):
    CORE = "CORE"
    ALTCOIN = "ALTCOIN"
    MID_CAP = "MID_CAP"
    SMALL_CAP = "SMALL_CAP"
    MEME = "MEME"


class MarketRegime(StrEnum):
    RISK_ON = "RISK_ON"
    NEUTRAL = "NEUTRAL"
    RISK_OFF = "RISK_OFF"


class DataQualityStatus(StrEnum):
    GOOD = "GOOD"
    WARNING = "WARNING"
    INVALID = "INVALID"


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
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


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


# Timeframe in minutes mapping
TIMEFRAME_MINUTES = {
    Timeframe.M5: 5,
    Timeframe.M15: 15,
    Timeframe.H1: 60,
    Timeframe.H4: 240,
    Timeframe.D1: 1440,
}
