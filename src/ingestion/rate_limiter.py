"""Token bucket rate limiting and dynamic backpressure per exchange — v3.0."""

from __future__ import annotations

import asyncio
import time

from src.utils.logging import get_logger

logger = get_logger("ingestion_rate_limiter")


class ExchangeRateLimiter:
    """Token bucket rate limiter enforcing request rate and 429/418 backoff per exchange."""

    def __init__(
        self,
        exchange_id: str,
        rate_limit_ms: int = 100,
        capacity: float = 10.0,
        default_backoff_seconds: float = 60.0,
    ) -> None:
        self.exchange_id = exchange_id
        self.rate_limit_ms = max(rate_limit_ms, 10)
        self.fill_rate = 1000.0 / self.rate_limit_ms  # requests per second
        self.capacity = max(capacity, 1.0)
        self.tokens = self.capacity
        self.last_update = time.monotonic()
        self.backoff_until = 0.0
        self.default_backoff_seconds = default_backoff_seconds
        self.rate_limit_count = 0
        self._lock = asyncio.Lock()

    def is_cooling_down(self) -> bool:
        """Return True if exchange is in backoff due to 429 or rate limit penalty."""
        return time.monotonic() < self.backoff_until

    def cooldown_remaining(self) -> float:
        """Return remaining backoff time in seconds, or 0.0."""
        return max(0.0, self.backoff_until - time.monotonic())

    def record_429(self, retry_after: float | None = None) -> float:
        """Record HTTP 429/418 response and dynamically set backoff timer."""
        self.rate_limit_count += 1
        wait_seconds = retry_after if retry_after is not None and retry_after > 0 else self.default_backoff_seconds
        self.backoff_until = time.monotonic() + wait_seconds
        logger.warning(
            "rate_limit_429_recorded",
            exchange=self.exchange_id,
            wait_seconds=wait_seconds,
            total_429_count=self.rate_limit_count,
        )
        return wait_seconds

    async def acquire(self) -> None:
        """Block until a token is available and any 429 backoff timer has cleared."""
        while True:
            now = time.monotonic()
            if now < self.backoff_until:
                sleep_sec = self.backoff_until - now
                logger.info(
                    "rate_limiter_backoff_wait",
                    exchange=self.exchange_id,
                    sleep_seconds=round(sleep_sec, 2),
                )
                await asyncio.sleep(sleep_sec)
                continue

            async with self._lock:
                now = time.monotonic()
                if now < self.backoff_until:
                    continue

                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.capacity, self.tokens + (elapsed * self.fill_rate))

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return

                wait_sec = (1.0 - self.tokens) / self.fill_rate

            await asyncio.sleep(wait_sec)


class RateLimiterRegistry:
    """Singleton-style registry managing rate limiters across all exchanges."""

    def __init__(self, default_backoff_seconds: float = 60.0) -> None:
        self.limiters: dict[str, ExchangeRateLimiter] = {}
        self.default_backoff_seconds = default_backoff_seconds

    def get_limiter(self, exchange_id: str, rate_limit_ms: int = 100) -> ExchangeRateLimiter:
        """Retrieve or create an ExchangeRateLimiter."""
        clean_id = exchange_id.lower()
        if clean_id not in self.limiters:
            self.limiters[clean_id] = ExchangeRateLimiter(
                exchange_id=clean_id,
                rate_limit_ms=rate_limit_ms,
                default_backoff_seconds=self.default_backoff_seconds,
            )
        return self.limiters[clean_id]
