"""Live market data ingestion service — v2.0 / v3.0.

Key v3.0 changes:
- Ingestion safety check: aborts startup if LIVE_TRADING_ENABLED is True.
- Multi-exchange fallback router (binance -> coinbase -> kraken) with auto-recovery.
- Dynamic rate-limiting and backpressure handling.
- Exponential backoff with uniform jitter (initial 1s, max 60s, factor 2, jitter +/-20%).
- Heartbeat ping/pong monitoring flagging degraded connection on timeout.
- Explicit data_mode persistence on all ingested OHLCV records.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import DataMode, Timeframe
from src.config.exceptions import DataUnavailableError
from src.config.settings import get_settings
from src.database.models import OHLCV
from src.database.session import get_session_factory, init_db
from src.features.pipeline import calculate_and_store_asset_features
from src.ingestion.pipeline import DEFAULT_UNIVERSE
from src.ingestion.providers.ccxt_provider import CCXTProvider
from src.ingestion.resilience import (
    ConnectionHealth,
    ExchangeFallbackManager,
    WebSocketHeartbeatMonitor,
    calculate_backoff_with_jitter,
)
from src.scoring.engine import score_universe
from src.utils.logging import get_logger
from src.utils.time import to_utc_datetime
from src.validation.ohlcv_validator import OHLCVValidator

if TYPE_CHECKING:
    from src.ingestion.providers.base import RawCandle

logger = get_logger("live_ingestor")
settings = get_settings()


def validate_ingestion_safety() -> None:
    """Abort ingestion if live real-money trading is somehow enabled."""
    if settings.LIVE_TRADING_ENABLED:
        raise RuntimeError(
            "CRITICAL: LIVE_TRADING_ENABLED=True detected. "
            "Ingestion is architecturally restricted to research and paper trading only. "
            "Aborting startup."
        )


class LiveIngestionResult:
    """Summary of one ingestion cycle."""

    def __init__(self, exchange: str | None = None) -> None:
        self.data_mode: DataMode = settings.DATA_MODE
        self.ingestion_started_at: datetime = datetime.now(UTC)
        self.ingestion_completed_at: datetime | None = None
        self.assets_attempted: int = 0
        self.assets_succeeded: int = 0
        self.assets_failed: int = 0
        self.total_candles_stored: int = 0
        self.errors: list[dict] = []
        self.exchange: str = exchange or settings.DEFAULT_EXCHANGE

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
    data_mode: str = "LIVE",
) -> int:
    """Fetch, validate, and store OHLCV candles for a single asset.

    Raises DataUnavailableError if exchange cannot supply data.
    Never generates or returns synthetic candles.
    """
    raw_candles = await provider.fetch_ohlcv(
        symbol=market_symbol,
        timeframe=timeframe.value,
        limit=limit,
    )

    from src.ingestion.providers.base import RawCandle as RawOHLCV

    ohlcv_inputs: list[RawCandle] = [
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
            existing.data_mode = data_mode
        else:
            session.add(
                OHLCV(
                    time=candle_dt,
                    market_id=market_id,
                    timeframe=timeframe.value,
                    open=c.open,
                    high=c.high,
                    low=c.low,
                    close=c.close,
                    volume=c.volume,
                    validation_status=c.validation_status.value,
                    data_mode=data_mode,
                )
            )
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
    fallback_manager: ExchangeFallbackManager | None = None,
) -> LiveIngestionResult:
    """Run one complete ingestion cycle for the tracked universe with multi-exchange fallback."""
    validate_ingestion_safety()

    f_mgr = fallback_manager or ExchangeFallbackManager(settings=settings)
    active_exchange = exchange_id or f_mgr.active_exchange

    result = LiveIngestionResult(exchange=active_exchange)

    logger.info(
        "ingestion_cycle_started",
        exchange=active_exchange,
        timeframe=timeframe.value,
        assets=len(DEFAULT_UNIVERSE),
        data_mode=result.data_mode,
    )

    owns_provider = _provider is None
    provider = _provider if _provider is not None else CCXTProvider(exchange_id=active_exchange)
    factory = get_session_factory()

    try:
        for item in DEFAULT_UNIVERSE:
            asset_id = item["id"]
            market_symbol = item["market"]
            market_id = f"{provider.exchange_id}:{market_symbol}"
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
                        data_mode=settings.DATA_MODE.value,
                    )
                result.total_candles_stored += count
                result.assets_succeeded += 1
                f_mgr.record_success(provider.exchange_id)
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
                # Check for rate-limit 429 or failure trigger
                is_429 = "429" in str(e) or e.reason == "RATE_LIMIT_429"
                async with factory() as session:
                    new_ex = await f_mgr.record_failure(
                        session=session,
                        exchange=provider.exchange_id,
                        reason=e.reason,
                        details=str(e),
                        is_429=is_429,
                    )
                if new_ex != provider.exchange_id:
                    logger.warning("switching_active_provider_after_failover", old=provider.exchange_id, new=new_ex)
                    if owns_provider:
                        await provider.close()
                    provider = CCXTProvider(exchange_id=new_ex)
                    result.exchange = new_ex

            except Exception as e:
                result.assets_failed += 1
                result.errors.append({"asset": asset_id, "reason": "UNEXPECTED_ERROR", "details": str(e)})
                logger.error("asset_ingestion_unexpected_error", asset=asset_id, error=str(e))
                async with factory() as session:
                    new_ex = await f_mgr.record_failure(
                        session=session,
                        exchange=provider.exchange_id,
                        reason="UNEXPECTED_ERROR",
                        details=str(e),
                    )
                if new_ex != provider.exchange_id:
                    if owns_provider:
                        await provider.close()
                    provider = CCXTProvider(exchange_id=new_ex)
                    result.exchange = new_ex

        # Compute features and scores
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
    fallback_manager: ExchangeFallbackManager | None = None,
    heartbeat_monitor: WebSocketHeartbeatMonitor | None = None,
    max_cycles: int | None = None,
) -> None:
    """Run continuous ingestion loop with exponential backoff + jitter and heartbeat monitoring."""
    validate_ingestion_safety()
    await init_db()

    f_mgr = fallback_manager or ExchangeFallbackManager(settings=settings)
    hb_monitor = heartbeat_monitor or WebSocketHeartbeatMonitor(
        timeout_seconds=float(settings.WS_HEARTBEAT_TIMEOUT)
    )

    consecutive_errors = 0
    cycles_completed = 0

    logger.info(
        "continuous_ingestion_started",
        interval_seconds=interval_seconds,
        primary_exchange=f_mgr.primary_exchange,
    )

    factory = get_session_factory()

    while max_cycles is None or cycles_completed < max_cycles:
        # Check auto-recovery to primary
        async with factory() as session:
            await f_mgr.check_auto_recovery(session)

        curr_exchange = f_mgr.active_exchange
        provider = CCXTProvider(exchange_id=curr_exchange)

        try:
            result = await run_ingestion_cycle(
                timeframe=timeframe,
                compute_features=True,
                compute_scores=True,
                exchange_id=curr_exchange,
                _provider=provider,
                fallback_manager=f_mgr,
            )

            hb_monitor.record_message()
            consecutive_errors = 0
            cycles_completed += 1

            health = hb_monitor.check_health()
            if health == ConnectionHealth.DEGRADED:
                logger.warning("ingestion_connection_degraded", exchange=curr_exchange)

            logger.info("ingestion_cycle_success", exchange=result.exchange, candles=result.total_candles_stored)
            await asyncio.sleep(interval_seconds)

        except Exception as e:
            consecutive_errors += 1
            health = hb_monitor.check_health()
            backoff_delay = calculate_backoff_with_jitter(
                attempt=consecutive_errors,
                initial=1.0,
                max_backoff=60.0,
                factor=2.0,
                jitter_pct=0.20,
            )
            logger.error(
                "ingestion_cycle_error",
                error=str(e),
                attempt=consecutive_errors,
                backoff_seconds=round(backoff_delay, 2),
                health=health.value,
            )
            await asyncio.sleep(backoff_delay)

        finally:
            await provider.close()


if __name__ == "__main__":
    asyncio.run(run_continuous_ingestion())
