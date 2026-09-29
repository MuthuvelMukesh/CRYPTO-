"""Unit tests for configuration and settings."""

from src.config.constants import (
    AssetClass,
    DataQualityStatus,
    MarketRegime,
    OrderSide,
    OrderStatus,
    OrderType,
    RiskFlag,
    Timeframe,
)
from src.config.settings import Settings


def test_settings_defaults():
    """Verify default configuration values."""
    s = Settings()
    assert s.APP_NAME == "Crypto Intelligence Platform"
    assert s.PAPER_INITIAL_CAPITAL == 100000.0
    assert s.MAKER_FEE_BPS == 2.0
    assert s.TAKER_FEE_BPS == 5.0
    assert s.is_sqlite is True
    assert "1h" in s.supported_timeframes_list
    assert "binance" in s.public_exchanges_list


def test_constants_and_enums():
    """Verify core domain enum values."""
    assert AssetClass.CORE == "CORE"
    assert AssetClass.MEME == "MEME"
    assert MarketRegime.RISK_ON == "RISK_ON"
    assert MarketRegime.RISK_OFF == "RISK_OFF"
    assert DataQualityStatus.GOOD == "GOOD"
    assert OrderType.MARKET == "MARKET"
    assert OrderSide.BUY == "BUY"
    assert OrderStatus.FILLED == "FILLED"
    assert Timeframe.H1 == "1h"
    assert RiskFlag.VERY_NEW == "VERY_NEW"
