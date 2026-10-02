"""Unit tests for Phase 3: Live market ingestion hardening, rate limiting, and resilience."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import OHLCV, Asset, ExchangeFailover, Market
from src.ingestion.live_ingestor import ingest_candles_for_asset, validate_ingestion_safety
from src.ingestion.rate_limiter import ExchangeRateLimiter
from src.ingestion.resilience import (
    ConnectionHealth,
    ExchangeFallbackManager,
    WebSocketHeartbeatMonitor,
    calculate_backoff_with_jitter,
)
from src.utils.time import utc_now


def test_exponential_backoff_with_jitter_bounds() -> None:
    """Backoff calculation must be bounded within +/- 20% jitter and capped at 60s."""
    # Attempt 0: base 1s -> [0.8, 1.2]
    val_min = calculate_backoff_with_jitter(attempt=0, initial=1.0, random_fn=lambda: 0.0)
    val_max = calculate_backoff_with_jitter(attempt=0, initial=1.0, random_fn=lambda: 1.0)
    assert pytest.approx(val_min, rel=1e-3) == 0.8
    assert pytest.approx(val_max, rel=1e-3) == 1.2

    # Attempt 1: base 2s -> [1.6, 2.4]
    val_min1 = calculate_backoff_with_jitter(attempt=1, initial=1.0, random_fn=lambda: 0.0)
    val_max1 = calculate_backoff_with_jitter(attempt=1, initial=1.0, random_fn=lambda: 1.0)
    assert pytest.approx(val_min1, rel=1e-3) == 1.6
    assert pytest.approx(val_max1, rel=1e-3) == 2.4

    # Attempt 6: 1.0 * (2^6) = 64 > max_backoff (60s) -> capped at 60s -> [48, 72]
    val_capped_min = calculate_backoff_with_jitter(attempt=6, max_backoff=60.0, random_fn=lambda: 0.0)
    val_capped_max = calculate_backoff_with_jitter(attempt=6, max_backoff=60.0, random_fn=lambda: 1.0)
    assert pytest.approx(val_capped_min, rel=1e-3) == 48.0
    assert pytest.approx(val_capped_max, rel=1e-3) == 72.0


@pytest.mark.asyncio
async def test_mock_exchange_429_triggers_failover(db_session: AsyncSession) -> None:
    """An HTTP 429 response must immediately trigger failover to the secondary exchange."""
    mgr = ExchangeFallbackManager(
        primary_exchange="binance",
        fallback_order=["binance", "coinbase", "kraken"],
    )
    assert mgr.active_exchange == "binance"

    # Simulate HTTP 429 error
    new_ex = await mgr.record_failure(
        session=db_session,
        exchange="binance",
        reason="RATE_LIMIT_429",
        details="Too many requests (HTTP 429)",
        is_429=True,
    )
    assert new_ex == "coinbase"
    assert mgr.active_exchange == "coinbase"
    assert len(mgr.failover_history) == 1

    # Verify failover logged to DB table exchange_failovers
    stmt = select(ExchangeFailover).where(ExchangeFailover.from_exchange == "binance")
    res = await db_session.execute(stmt)
    records = res.scalars().all()
    assert len(records) == 1
    assert records[0].to_exchange == "coinbase"
    assert records[0].reason == "RATE_LIMIT_429"


@pytest.mark.asyncio
async def test_consecutive_failures_trigger_failover(db_session: AsyncSession) -> None:
    """3 consecutive connection failures must fail over to the next exchange."""
    mgr = ExchangeFallbackManager(
        primary_exchange="binance",
        fallback_order=["binance", "coinbase", "kraken"],
        consecutive_failure_threshold=3,
    )
    # Failures 1 & 2: remain on binance
    await mgr.record_failure(session=db_session, exchange="binance", reason="TIMEOUT")
    assert mgr.active_exchange == "binance"
    await mgr.record_failure(session=db_session, exchange="binance", reason="TIMEOUT")
    assert mgr.active_exchange == "binance"

    # Failure 3: triggers failover to coinbase
    new_ex = await mgr.record_failure(session=db_session, exchange="binance", reason="TIMEOUT")
    assert new_ex == "coinbase"
    assert mgr.active_exchange == "coinbase"


@pytest.mark.asyncio
async def test_exchange_recovery_to_primary_after_cooldown(db_session: AsyncSession) -> None:
    """After failover, manager must auto-recover to primary once cooldown expires."""
    cooldown = 100.0
    mgr = ExchangeFallbackManager(
        primary_exchange="binance",
        fallback_order=["binance", "coinbase", "kraken"],
        cooldown_seconds=cooldown,
    )
    start_time = 1000.0

    # Fail over to coinbase
    with patch("time.monotonic", return_value=start_time):
        await mgr.record_failure(session=db_session, is_429=True)
    assert mgr.active_exchange == "coinbase"

    # 50s later: cooldown not reached -> no recovery
    with patch("time.monotonic", return_value=start_time + 50.0):
        recovered = await mgr.check_auto_recovery(session=db_session, now=start_time + 50.0)
    assert recovered is False
    assert mgr.active_exchange == "coinbase"

    # 105s later: cooldown elapsed -> auto-recovers to binance
    with patch("time.monotonic", return_value=start_time + 105.0):
        recovered = await mgr.check_auto_recovery(session=db_session, now=start_time + 105.0)
    assert recovered is True
    assert mgr.active_exchange == "binance"


def test_heartbeat_detects_silent_disconnect() -> None:
    """Heartbeat monitor must detect hung TCP socket when elapsed time exceeds timeout."""
    monitor = WebSocketHeartbeatMonitor(timeout_seconds=30.0)
    start = 1000.0
    monitor.last_message_at = start

    # 10s elapsed: connection is healthy
    assert monitor.check_health(now=start + 10.0) == ConnectionHealth.CONNECTED

    # 35s elapsed (> 30s timeout): connection degraded (hung socket)
    assert monitor.check_health(now=start + 35.0) == ConnectionHealth.DEGRADED

    # New message received: recovers to CONNECTED
    with patch("time.monotonic", return_value=start + 36.0):
        monitor.record_message()
    assert monitor.check_health(now=start + 36.0) == ConnectionHealth.CONNECTED


def test_token_bucket_rate_limiter_backoff() -> None:
    """Rate limiter must enter backoff mode upon receiving HTTP 429."""
    limiter = ExchangeRateLimiter(exchange_id="binance", default_backoff_seconds=60.0)
    assert limiter.is_cooling_down() is False

    wait = limiter.record_429(retry_after=45.0)
    assert wait == 45.0
    assert limiter.is_cooling_down() is True
    assert limiter.cooldown_remaining() > 40.0


def test_ingestion_aborts_if_live_trading_enabled() -> None:
    """Ingestion safety guard must abort startup if LIVE_TRADING_ENABLED is True."""
    with patch("src.ingestion.live_ingestor.settings") as mock_settings:
        mock_settings.LIVE_TRADING_ENABLED = True
        with pytest.raises(RuntimeError) as exc_info:
            validate_ingestion_safety()
        assert "LIVE_TRADING_ENABLED=True detected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ingested_candles_carry_data_mode(db_session: AsyncSession) -> None:
    """Ingested candles must explicitly store data_mode='LIVE'."""
    now_dt = utc_now()

    # Seed asset and market
    db_session.add(Asset(id="BTC", name="Bitcoin", symbol="BTC", asset_class="CORE", primary_sector="Layer 1"))
    db_session.add(Market(id="binance:BTC/USDT", exchange_id="binance", asset_id="BTC", quote_asset="USDT", symbol="BTC/USDT"))
    await db_session.commit()

    mock_provider = MagicMock()
    mock_provider.exchange_id = "binance"
    mock_provider.fetch_ohlcv = AsyncMock(
        return_value=[
            {
                "time_ms": int(now_dt.timestamp() * 1000),
                "open": 65000.0,
                "high": 65200.0,
                "low": 64800.0,
                "close": 65100.0,
                "volume": 50.0,
            }
        ]
    )

    count = await ingest_candles_for_asset(
        session=db_session,
        provider=mock_provider,
        asset_id="BTC",
        market_symbol="BTC/USDT",
        market_id="binance:BTC/USDT",
        data_mode="LIVE",
    )
    assert count == 1

    candle = (
        await db_session.execute(
            select(OHLCV).where(OHLCV.market_id == "binance:BTC/USDT")
        )
    ).scalar_one()

    assert candle.data_mode == "LIVE"
    assert candle.close == 65100.0
