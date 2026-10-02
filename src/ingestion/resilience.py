"""Ingestion resilience: exponential backoff with jitter, multi-exchange failover, and heartbeat monitoring — v3.0."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import ExchangeFailover
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.config.settings import Settings

logger = get_logger("ingestion_resilience")


def calculate_backoff_with_jitter(
    attempt: int,
    initial: float = 1.0,
    max_backoff: float = 60.0,
    factor: float = 2.0,
    jitter_pct: float = 0.20,
    random_fn: Callable[[], float] | None = None,
) -> float:
    """Calculate exponential backoff with uniform jitter (± jitter_pct).

    Args:
        attempt: 0-indexed attempt count.
        initial: starting delay in seconds.
        max_backoff: delay ceiling in seconds.
        factor: exponential multiplier.
        jitter_pct: maximum fractional deviation (e.g. 0.20 for ±20%).
        random_fn: optional RNG producing [0, 1) for deterministic testing.
    """
    base = min(max_backoff, initial * (factor**attempt))
    if random_fn is not None:
        r = random_fn()
        jitter_delta = (r * 2.0 - 1.0) * jitter_pct
    else:
        jitter_delta = random.uniform(-jitter_pct, jitter_pct)
    return max(0.0, base * (1.0 + jitter_delta))


class ConnectionHealth(StrEnum):
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    DISCONNECTED = "DISCONNECTED"


class WebSocketHeartbeatMonitor:
    """Tracks message frequency and flags silent disconnects (hung TCP sockets)."""

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.last_message_at = time.monotonic()
        self.status = ConnectionHealth.CONNECTED

    def record_message(self) -> None:
        """Record receipt of a valid message or ping/pong frame."""
        self.last_message_at = time.monotonic()
        self.status = ConnectionHealth.CONNECTED

    def check_health(self, now: float | None = None) -> ConnectionHealth:
        """Inspect elapsed time since last message. Returns DEGRADED if timed out."""
        curr = now if now is not None else time.monotonic()
        elapsed = curr - self.last_message_at
        if elapsed > self.timeout_seconds:
            if self.status != ConnectionHealth.DEGRADED:
                logger.warning(
                    "websocket_connection_degraded",
                    elapsed_seconds=round(elapsed, 2),
                    timeout_seconds=self.timeout_seconds,
                )
            self.status = ConnectionHealth.DEGRADED
        else:
            self.status = ConnectionHealth.CONNECTED
        return self.status

    def mark_disconnected(self) -> None:
        self.status = ConnectionHealth.DISCONNECTED


class ExchangeFallbackManager:
    """Multi-exchange failover controller with automatic primary recovery.

    Fallback sequence: binance -> coinbase -> kraken.
    Triggers failover on:
    - 3 consecutive connection failures
    - HTTP 429 rate limit error
    """

    def __init__(
        self,
        primary_exchange: str = "binance",
        fallback_order: list[str] | None = None,
        cooldown_seconds: float = 900.0,  # 15 minutes
        consecutive_failure_threshold: int = 3,
        settings: Settings | None = None,
    ) -> None:
        if settings is not None:
            self.fallback_order = [ex.lower() for ex in settings.exchange_fallback_order_list]
            self.cooldown_seconds = float(settings.EXCHANGE_FAILOVER_COOLDOWN_SECONDS)
        else:
            self.fallback_order = [ex.lower() for ex in (fallback_order or ["binance", "coinbase", "kraken"])]
            self.cooldown_seconds = cooldown_seconds

        self.primary_exchange = primary_exchange.lower()
        if self.primary_exchange not in self.fallback_order:
            self.fallback_order.insert(0, self.primary_exchange)

        self.current_exchange_idx = self.fallback_order.index(self.primary_exchange)
        self.consecutive_failure_threshold = consecutive_failure_threshold
        self.consecutive_failures: dict[str, int] = dict.fromkeys(self.fallback_order, 0)
        self.last_failover_time: float | None = None
        self.failover_history: list[dict[str, Any]] = []

    @property
    def active_exchange(self) -> str:
        return self.fallback_order[self.current_exchange_idx]

    def is_on_primary(self) -> bool:
        return self.active_exchange == self.primary_exchange

    def record_success(self, exchange: str | None = None) -> None:
        """Reset failure counter on successful request."""
        ex = (exchange or self.active_exchange).lower()
        if ex in self.consecutive_failures:
            self.consecutive_failures[ex] = 0

    async def record_failure(
        self,
        session: AsyncSession | None = None,
        exchange: str | None = None,
        reason: str = "CONNECTION_FAILURE",
        details: str | None = None,
        is_429: bool = False,
    ) -> str:
        """Record an exchange failure and trigger failover if threshold reached.

        Returns the active exchange (either unchanged or new after failover).
        """
        ex = (exchange or self.active_exchange).lower()
        self.consecutive_failures[ex] = self.consecutive_failures.get(ex, 0) + 1

        should_failover = is_429 or (self.consecutive_failures[ex] >= self.consecutive_failure_threshold)

        if should_failover:
            old_exchange = ex
            # Advance to next available fallback exchange
            next_idx = (self.current_exchange_idx + 1) % len(self.fallback_order)
            new_exchange = self.fallback_order[next_idx]
            self.current_exchange_idx = next_idx
            self.last_failover_time = time.monotonic()

            failover_record = {
                "from_exchange": old_exchange,
                "to_exchange": new_exchange,
                "reason": "RATE_LIMIT_429" if is_429 else reason,
                "details": details or f"Triggered after {self.consecutive_failures[old_exchange]} failures",
                "timestamp": datetime.now(UTC),
            }
            self.failover_history.append(failover_record)

            logger.warning(
                "exchange_failover_triggered",
                from_exchange=old_exchange,
                to_exchange=new_exchange,
                reason=failover_record["reason"],
                details=failover_record["details"],
            )

            # Persist to database if session provided
            if session is not None:
                try:
                    db_event = ExchangeFailover(
                        from_exchange=old_exchange,
                        to_exchange=new_exchange,
                        reason=failover_record["reason"],
                        details=failover_record["details"],
                    )
                    session.add(db_event)
                    await session.commit()
                except Exception as e:
                    logger.error("failed_to_log_exchange_failover_to_db", error=str(e))

        return self.active_exchange

    async def check_auto_recovery(
        self,
        session: AsyncSession | None = None,
        now: float | None = None,
    ) -> bool:
        """Attempt recovery back to primary exchange if cooldown has elapsed."""
        if self.is_on_primary() or self.last_failover_time is None:
            return False

        curr_time = now if now is not None else time.monotonic()
        elapsed = curr_time - self.last_failover_time

        if elapsed >= self.cooldown_seconds:
            old_exchange = self.active_exchange
            self.current_exchange_idx = self.fallback_order.index(self.primary_exchange)
            self.consecutive_failures[self.primary_exchange] = 0
            self.last_failover_time = None

            logger.info(
                "exchange_auto_recovered_to_primary",
                from_exchange=old_exchange,
                to_exchange=self.primary_exchange,
                elapsed_seconds=round(elapsed, 1),
            )

            if session is not None:
                try:
                    db_event = ExchangeFailover(
                        from_exchange=old_exchange,
                        to_exchange=self.primary_exchange,
                        reason="AUTO_RECOVERY",
                        details=f"Cooldown of {self.cooldown_seconds}s elapsed. Returned to primary exchange.",
                    )
                    session.add(db_event)
                    await session.commit()
                except Exception as e:
                    logger.error("failed_to_log_exchange_recovery_to_db", error=str(e))

            return True

        return False
