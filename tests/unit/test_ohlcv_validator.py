"""Unit tests for OHLCV data validation engine."""

import time

from src.config.constants import DataQualityStatus, Timeframe
from src.ingestion.providers.base import RawCandle
from src.validation.ohlcv_validator import OHLCVValidator


def test_valid_candle_passes():
    """Verify that a physically valid candlestick passes validation."""
    now_ms = int(time.time() * 1000)
    candle = RawCandle(
        timestamp_ms=now_ms - 60000,
        open=100.0,
        high=105.0,
        low=98.0,
        close=103.0,
        volume=500.0,
    )
    result = OHLCVValidator.validate_candle(candle)
    assert result.is_valid is True
    assert result.status == DataQualityStatus.GOOD
    assert len(result.reasons) == 0


def test_non_positive_price_rejected():
    """Verify zero and negative prices are marked invalid."""
    now_ms = int(time.time() * 1000)
    candle_zero = RawCandle(
        timestamp_ms=now_ms - 60000,
        open=100.0,
        high=105.0,
        low=0.0,  # Zero price
        close=103.0,
        volume=10.0,
    )
    res_zero = OHLCVValidator.validate_candle(candle_zero)
    assert res_zero.is_valid is False
    assert "NON_POSITIVE_PRICE" in res_zero.reasons

    candle_neg = RawCandle(
        timestamp_ms=now_ms - 60000,
        open=100.0,
        high=105.0,
        low=-5.0,  # Negative price
        close=103.0,
        volume=10.0,
    )
    res_neg = OHLCVValidator.validate_candle(candle_neg)
    assert res_neg.is_valid is False
    assert "NON_POSITIVE_PRICE" in res_neg.reasons


def test_high_low_violation_rejected():
    """Verify high < low is caught."""
    now_ms = int(time.time() * 1000)
    candle = RawCandle(
        timestamp_ms=now_ms - 60000,
        open=100.0,
        high=90.0,  # high < low
        low=95.0,
        close=92.0,
        volume=10.0,
    )
    res = OHLCVValidator.validate_candle(candle)
    assert res.is_valid is False
    assert "HIGH_LESS_THAN_LOW" in res.reasons


def test_negative_volume_rejected():
    """Verify negative volume is rejected."""
    now_ms = int(time.time() * 1000)
    candle = RawCandle(
        timestamp_ms=now_ms - 60000,
        open=100.0,
        high=105.0,
        low=95.0,
        close=102.0,
        volume=-1.0,  # Negative volume
    )
    res = OHLCVValidator.validate_candle(candle)
    assert res.is_valid is False
    assert "NEGATIVE_VOLUME" in res.reasons


def test_future_timestamp_rejected():
    """Verify candles with timestamps in the far future are rejected."""
    far_future_ms = int(time.time() * 1000) + (86400 * 1000)  # Tomorrow
    candle = RawCandle(
        timestamp_ms=far_future_ms,
        open=100.0,
        high=105.0,
        low=95.0,
        close=102.0,
        volume=10.0,
    )
    res = OHLCVValidator.validate_candle(candle, max_future_skew_seconds=60)
    assert res.is_valid is False
    assert "FUTURE_TIMESTAMP" in res.reasons


def test_sequence_deduplication_and_gap_detection():
    """Verify duplicate candles are eliminated and gaps detected."""
    base_ms = 1700000000000
    candles = [
        # Normal candle 1
        RawCandle(timestamp_ms=base_ms, open=100.0, high=105.0, low=95.0, close=102.0, volume=10.0),
        # Duplicate candle 1
        RawCandle(timestamp_ms=base_ms, open=100.0, high=105.0, low=95.0, close=102.0, volume=10.0),
        # Normal candle 2 (1 hour later = +3,600,000 ms)
        RawCandle(timestamp_ms=base_ms + 3600000, open=102.0, high=108.0, low=101.0, close=107.0, volume=12.0),
        # Normal candle 3 with a 5-hour gap
        RawCandle(timestamp_ms=base_ms + (6 * 3600000), open=107.0, high=110.0, low=106.0, close=109.0, volume=15.0),
    ]

    cleaned, warnings = OHLCVValidator.validate_and_clean_series(candles, timeframe=Timeframe.H1)
    # Deduplication check
    assert len(cleaned) == 3
    assert any("DUPLICATE" in w for w in warnings)
    # Gap check
    assert any("GAP" in w for w in warnings)
