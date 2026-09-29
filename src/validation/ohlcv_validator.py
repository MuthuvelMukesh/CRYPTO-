"""Data quality and integrity validation engine for OHLCV candlesticks."""

from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel

from src.config.constants import TIMEFRAME_MINUTES, DataQualityStatus, Timeframe
from src.ingestion.providers.base import RawCandle
from src.utils.logging import get_logger
from src.utils.time import to_utc_datetime, utc_now

logger = get_logger("validation.ohlcv")


class ValidationResult(BaseModel):
    is_valid: bool
    status: DataQualityStatus
    reasons: list[str]


class OHLCVValidator:
    """Rigorous financial time-series integrity validator."""

    @classmethod
    def validate_candle(
        cls,
        candle: RawCandle,
        max_future_skew_seconds: int = 300,
    ) -> ValidationResult:
        """Validate single candlestick OHLC relationships and physical boundaries."""
        reasons: list[str] = []

        # 1. Non-positive price check
        if candle.open <= 0 or candle.high <= 0 or candle.low <= 0 or candle.close <= 0:
            reasons.append("NON_POSITIVE_PRICE")

        # 2. High vs Low integrity
        if candle.high < candle.low:
            reasons.append("HIGH_LESS_THAN_LOW")

        # 3. High must bound Open and Close
        if candle.high < candle.open or candle.high < candle.close:
            reasons.append("HIGH_LOWER_THAN_OPEN_OR_CLOSE")

        # 4. Low must bound Open and Close
        if candle.low > candle.open or candle.low > candle.close:
            reasons.append("LOW_HIGHER_THAN_OPEN_OR_CLOSE")

        # 5. Non-negative volume
        if candle.volume < 0:
            reasons.append("NEGATIVE_VOLUME")

        # 6. Future timestamp check
        candle_dt = to_utc_datetime(candle.timestamp_ms)
        now_dt = utc_now()
        if (candle_dt - now_dt).total_seconds() > max_future_skew_seconds:
            reasons.append("FUTURE_TIMESTAMP")

        if reasons:
            return ValidationResult(
                is_valid=False,
                status=DataQualityStatus.INVALID,
                reasons=reasons,
            )

        return ValidationResult(
            is_valid=True,
            status=DataQualityStatus.GOOD,
            reasons=[],
        )

    @classmethod
    def validate_and_clean_series(
        cls,
        candles: Sequence[RawCandle],
        timeframe: Timeframe = Timeframe.H1,
    ) -> tuple[list[RawCandle], list[str]]:
        """
        Validate, deduplicate, and check sequence gaps for a series of candlesticks.
        Returns cleaned sequence of valid candles and any detected sequence-level warnings.
        """
        if not candles:
            return [], ["EMPTY_SERIES"]

        warnings: list[str] = []

        # Sort chronologically
        sorted_candles = sorted(candles, key=lambda c: c.timestamp_ms)

        # 1. Deduplicate by timestamp and validate individual candles
        cleaned: list[RawCandle] = []
        seen_timestamps: set[int] = set()
        duplicates_count = 0

        for c in sorted_candles:
            if c.timestamp_ms in seen_timestamps:
                duplicates_count += 1
                continue

            val_res = cls.validate_candle(c)
            if not val_res.is_valid:
                logger.warning(
                    "corrupt_candle_rejected",
                    timestamp=c.timestamp_ms,
                    reasons=val_res.reasons,
                )
                continue

            seen_timestamps.add(c.timestamp_ms)
            c.validation_status = val_res.status
            cleaned.append(c)

        if duplicates_count > 0:
            warnings.append(f"REMOVED_{duplicates_count}_DUPLICATE_CANDLES")

        if len(cleaned) < 2:
            return cleaned, warnings

        # 2. Check for sequence gaps
        expected_interval_ms = TIMEFRAME_MINUTES.get(timeframe, 60) * 60 * 1000
        gaps_detected = 0

        for i in range(1, len(cleaned)):
            delta = cleaned[i].timestamp_ms - cleaned[i - 1].timestamp_ms
            # Allow 10% drift for minor exchange latency
            if delta > expected_interval_ms * 1.5:
                gaps_detected += 1

        if gaps_detected > 0:
            warnings.append(f"DETECTED_{gaps_detected}_TIMESTAMPS_GAPS")

        # 3. Anomaly check: volume outlier vs median
        volumes = [c.volume for c in cleaned if c.volume > 0]
        if volumes:
            median_vol = float(np.median(volumes))
            for c in cleaned:
                if median_vol > 0 and (c.volume / median_vol) > 50.0:
                    c.validation_status = DataQualityStatus.WARNING

        return cleaned, warnings
