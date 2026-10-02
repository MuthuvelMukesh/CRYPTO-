"""Live market data ingestion service — v2.0.

This module provides the real-time OHLCV ingestion loop using CCXT.
It fetches candles for all tracked assets, validates them, and stores
them with provenance metadata.

Provenance chain:
  CCXTProvider.fetch_ohlcv() → OHLCVValidator → OHLCV table → Feature pipeline
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import DataMode, Timeframe
from src.config.exceptions import DataUnavailableError
from src.config.settings import get_settings
from src.database.models import OHLCV
from src.database.session import get_session_factory, init_db
from src.features.pipeline import calculate_and_store_asset_features
from src.ingestion.pipeline import DEFAULT_UNIVERSE
from src.ingestion.providers.ccxt_provider import CCXTProvider
from src.scoring.engine import score_universe
from src.utils.logging import get_logger
from src.utils.time import to_utc_datetime
from src.validation.ohlcv_validator import OHLCVValidator

logger = get_logger("live_ingestor")
settings = get_settings()


class LiveIngestionResult:
    """Summary of one ingestion cycle."""

    def __init__(self) -> None:
        self.data_mode: DataMode = settings.DATA_MODE
        self.ingestion_started_at: datetime = datetime.now(UTC)
        self.ingestion_completed_at: datetime | None = None
        self.assets_attempted: int = 0
        self.assets_succeeded: int = 0
        self.assets_failed: int = 0
        self.total_candles_stored: int = 0
        self.errors: list[dict] = []
        self.exchange: str = settings.DEFAULT_EXCHANGE

    def complete(self) -> None:
        self.ingestion_completed_at = datetime.now(UTC)

    @property
    def duration_seconds(self) -> float:
        if self.ingestion_completed_at:
            return (self.ingestion_completed_at - self.ingestion_started_at).total_seconds()
        return 0.0


async def ingest_candles_for_asset(
    session: AsyncSession,
    provider: CCXTProvider,
    asset_id: str,
    market_symbol: str,
    market_id: str,
    timeframe: Timeframe = Timeframe.H1,
    limit: int = 200,
) -> int:
    """Fetch, validate, and store OHLCV candles for a single asset.

    Raises DataUnavailableError if exchange cannot supply data.
    Never generates or returns synthetic candles.

    Returns:
        Number of candles stored.
    """
    raw_candles = await provider.fetch_ohlcv(
        symbol=market_symbol,
        timeframe=timeframe.value,
        limit=limit,
    )

    # raw_candles is list of {time_ms, open, high, low, close, volume}
    # Convert to the format OHLCVValidator expects
    from src.ingestion.providers.base import RawCandle as RawOHLCV

    ohlcv_inputs = [
        RawOHLCV(
            timestamp_ms=c["time_ms"],
            open=c["open"],
            high=c["high"],
            low=c["low"],
            close=c["close"],
            volume=c["volume"],
        )
        for c in raw_candles
    ]

    cleaned, warnings = OHLCVValidator.validate_and_clean_series(ohlcv_inputs, timeframe=timeframe)

    if warnings:
        logger.info("ohlcv_validation_warnings", asset=asset_id, count=len(warnings))

    saved_count = 0

    for c in cleaned:
        candle_dt = to_utc_datetime(c.timestamp_ms)

        from sqlalchemy import select
        existing_res = await session.execute(
            select(OHLCV).where(
                OHLCV.market_id == market_id,
                OHLCV.timeframe == timeframe.value,
                OHLCV.time == candle_dt,
            )
        )
        existing = existing_res.scalar_one_or_none()
        if existing:
            existing.open = c.open
            existing.high = c.high
            existing.low = c.low
            existing.close = c.close
            existing.volume = c.volume
            existing.validation_status = c.validation_status.value
        else:
            session.add(OHLCV(
                time=candle_dt,
                market_id=market_id,
                timeframe=timeframe.value,
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
                validation_status=c.validation_status.value,
            ))
        saved_count += 1

    await session.commit()
    return saved_count


async def run_ingestion_cycle(
    timeframe: Timeframe = Timeframe.H1,
    compute_features: bool = True,
    compute_scores: bool = True,
    exchange_id: str | None = None,
    limit: int = 200,
    _provider: CCXTProvider | None = None,
) -> LiveIngestionResult:
    """Run one complete ingestion cycle for the tracked universe.

    Args:
        _provider: optional pre-existing CCXTProvider to reuse (for continuous mode).
                   If None, a new provider is created and closed after the cycle.
    """
    result = LiveIngestionResult()
    exchange = exchange_id or settings.DEFAULT_EXCHANGE
    result.exchange = exchange

    logger.info(
        "ingestion_cycle_started",
        exchange=exchange,
        timeframe=timeframe.value,
        assets=len(DEFAULT_UNIVERSE),
        data_mode=result.data_mode,
    )

    # Use injected provider or create a temporary one
    owns_provider = _provider is None
    provider = _provider if _provider is not None else CCXTProvider(exchange_id=exchange)
    factory = get_session_factory()

    try:
        for item in DEFAULT_UNIVERSE:
            asset_id = item["id"]
            market_symbol = item["market"]  # e.g. "BTC/USDT"
            market_id = f"{exchange}:{market_symbol}"
            result.assets_attempted += 1

            try:
                async with factory() as session:
                    count = await ingest_candles_for_asset(
                        session=session,
                        provider=provider,
                        asset_id=asset_id,
                        market_symbol=market_symbol,
                        market_id=market_id,
                        timeframe=timeframe,
                        limit=limit,
                    )
                result.total_candles_stored += count
                result.assets_succeeded += 1
                logger.info("asset_ingested", asset=asset_id, candles=count)

            except DataUnavailableError as e:
                result.assets_failed += 1
                result.errors.append({
                    "asset": asset_id,
                    "reason": e.reason,
                    "details": str(e),
                })
                logger.warning(
                    "asset_ingestion_failed",
                    asset=asset_id,
                    reason=e.reason,
                    details=str(e),
                )
            except Exception as e:
                result.assets_failed += 1
                result.errors.append({"asset": asset_id, "reason": "UNEXPECTED_ERROR", "details": str(e)})
                logger.error("asset_ingestion_unexpected_error", asset=asset_id, error=str(e))

        # Compute features and scores for all assets
        if compute_features and result.assets_succeeded > 0:
            async with factory() as session:
                for item in DEFAULT_UNIVERSE:
                    try:
                        await calculate_and_store_asset_features(session, item["id"], timeframe)
                    except Exception as e:
                        logger.warning("feature_computation_failed", asset=item["id"], error=str(e))

        if compute_scores and result.assets_succeeded > 0:
            async with factory() as session:
                try:
                    await score_universe(session, timeframe)
                except Exception as e:
                    logger.warning("score_computation_failed", error=str(e))

    finally:
        if owns_provider:
            await provider.close()

    result.complete()
    logger.info(
        "ingestion_cycle_completed",
        duration_seconds=result.duration_seconds,
        assets_succeeded=result.assets_succeeded,
        assets_failed=result.assets_failed,
        total_candles=result.total_candles_stored,
    )
    return result


async def run_continuous_ingestion(
    interval_seconds: int = 300,
    timeframe: Timeframe = Timeframe.H1,
) -> None:
    """Run the ingestion loop indefinitely with a single long-lived provider.

    The CCXTProvider is created once and kept open for the lifetime of the
    process. Each cycle shares the same authenticated exchange session,
    avoiding the overhead and errors of reconnecting per cycle.
    """
    await init_db()
    exchange = settings.DEFAULT_EXCHANGE
    provider = CCXTProvider(exchange_id=exchange)

    logger.info(
        "continuous_ingestion_started",
        interval_seconds=interval_seconds,
        exchange=exchange,
    )

    try:
        while True:
            try:
                result = await run_ingestion_cycle(
                    timeframe=timeframe,
                    compute_features=True,
                    compute_scores=True,
                    _provider=provider,  # reuse existing connection
                )
                logger.info(
                    "ingestion_cycle_summary",
                    succeeded=result.assets_succeeded,
                    failed=result.assets_failed,
                    candles=result.total_candles_stored,
                    duration=result.duration_seconds,
                )
            except Exception as e:
                logger.error("ingestion_cycle_fatal_error", error=str(e))

            logger.info("ingestion_sleeping", seconds=interval_seconds)
            await asyncio.sleep(interval_seconds)
    finally:
        await provider.close()
        logger.info("continuous_ingestion_stopped")


if __name__ == "__main__":
    """Entry point for running the ingestion worker standalone."""
    asyncio.run(run_continuous_ingestion())

