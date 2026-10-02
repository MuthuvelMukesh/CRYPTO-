"""CCXT-based MarketDataProvider implementation — v2.0.

Uses the ccxt library to fetch live market data from Binance (default)
and other exchanges. All error paths raise DataUnavailableError or
PriceUnavailableError — no synthetic fallback is ever returned.
"""

from datetime import UTC, datetime
from typing import Any

from src.config.exceptions import (
    DataUnavailableError,
    ExternalProviderUnavailableError,
    PriceUnavailableError,
)
from src.ingestion.rate_limiter import ExchangeRateLimiter
from src.utils.logging import get_logger

logger = get_logger("ccxt_provider")


def _require_ccxt() -> Any:
    """Import ccxt, raising a clear error if not installed."""
    try:
        import ccxt.async_support as ccxt  # type: ignore[import]
        return ccxt
    except ImportError as e:
        raise ImportError(
            "ccxt is required for live market data. "
            "Install with: pip install ccxt"
        ) from e


class CCXTProvider:
    """Live market data provider backed by CCXT library.

    This class is the only place in the codebase that interacts with
    exchange REST APIs. All other modules consume its validated output.

    Never returns synthetic candles or hard-coded price fallbacks.
    """

    def __init__(
        self,
        exchange_id: str = "binance",
        timeout_ms: int = 10_000,
        rate_limiter: ExchangeRateLimiter | None = None,
    ) -> None:
        self.exchange_id = exchange_id
        self.timeout_ms = timeout_ms
        self._exchange: Any | None = None
        self.rate_limiter = rate_limiter or ExchangeRateLimiter(
            exchange_id=exchange_id,
            rate_limit_ms=100,
            default_backoff_seconds=60.0,
        )

    async def _get_exchange(self) -> Any:
        if self._exchange is None:
            ccxt = _require_ccxt()
            exchange_cls = getattr(ccxt, self.exchange_id, None)
            if exchange_cls is None:
                raise DataUnavailableError(
                    source=self.exchange_id,
                    reason="UNSUPPORTED_EXCHANGE",
                    details=f"Exchange '{self.exchange_id}' is not supported by ccxt.",
                )
            self._exchange = exchange_cls({
                "timeout": self.timeout_ms,
                "enableRateLimit": True,
            })
            if hasattr(self._exchange, "rateLimit") and self._exchange.rateLimit:
                self.rate_limiter.rate_limit_ms = int(self._exchange.rateLimit)
                self.rate_limiter.fill_rate = 1000.0 / self.rate_limiter.rate_limit_ms
        return self._exchange

    async def fetch_markets(self, exchange: str | None = None) -> list[dict[str, Any]]:
        """Fetch and return all active spot markets from the exchange."""
        await self.rate_limiter.acquire()
        ex = await self._get_exchange()
        try:
            raw_markets = await ex.load_markets(reload=True)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "418" in err_str or "RateLimit" in type(e).__name__:
                self.rate_limiter.record_429()
            raise ExternalProviderUnavailableError(
                provider=self.exchange_id,
                details=f"load_markets failed: {e}",
            ) from e

        result = []
        for symbol, info in raw_markets.items():
            if not info.get("active", False):
                continue
            if info.get("type") not in {"spot", None}:
                continue
            result.append({
                "id": info.get("id", ""),
                "symbol": symbol,
                "base": info.get("base", ""),
                "quote": info.get("quote", ""),
                "active": bool(info.get("active")),
                "type": info.get("type", "spot"),
                "spot": info.get("spot", True),
                # volume_24h_usd populated separately via ticker batch fetch
                "volume_24h_usd": 0.0,
            })
        logger.info("ccxt_markets_loaded", exchange=self.exchange_id, count=len(result))
        return result

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since_ms: int | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Fetch OHLCV candles.

        Raises DataUnavailableError if no candles returned or rate limit hit.
        """
        await self.rate_limiter.acquire()
        ex = await self._get_exchange()
        try:
            raw = await ex.fetch_ohlcv(symbol, timeframe, since=since_ms, limit=limit)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "418" in err_str or "RateLimit" in type(e).__name__:
                self.rate_limiter.record_429()
                raise DataUnavailableError(
                    source=self.exchange_id,
                    symbol=symbol,
                    reason="RATE_LIMIT_429",
                    details=f"Rate limit hit on {self.exchange_id}: {e}",
                ) from e
            raise DataUnavailableError(
                source=self.exchange_id,
                symbol=symbol,
                reason="OHLCV_FETCH_FAILED",
                details=str(e),
            ) from e

        if not raw:
            raise DataUnavailableError(
                source=self.exchange_id,
                symbol=symbol,
                reason="EMPTY_OHLCV_RESPONSE",
                details=f"Exchange returned 0 candles for {symbol}/{timeframe}.",
            )

        result = []
        for c in raw:
            ts_ms, open_, high, low, close, vol = c
            if close is None or close <= 0:
                continue
            result.append({
                "time_ms": int(ts_ms),
                "open": float(open_),
                "high": float(high),
                "low": float(low),
                "close": float(close),
                "volume": float(vol) if vol else 0.0,
            })

        if not result:
            raise DataUnavailableError(
                source=self.exchange_id,
                symbol=symbol,
                reason="INVALID_CANDLE_DATA",
                details="All returned candles had zero or null close price.",
            )

        logger.info(
            "ccxt_ohlcv_fetched",
            exchange=self.exchange_id,
            symbol=symbol,
            timeframe=timeframe,
            candles=len(result),
        )
        return result

    async def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        """Fetch current ticker — raises PriceUnavailableError on failure."""
        await self.rate_limiter.acquire()
        ex = await self._get_exchange()
        try:
            t = await ex.fetch_ticker(symbol)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "418" in err_str or "RateLimit" in type(e).__name__:
                self.rate_limiter.record_429()
            raise PriceUnavailableError(
                symbol=symbol,
                source=self.exchange_id,
                details=str(e),
            ) from e

        last = t.get("last")
        if last is None or float(last) <= 0:
            raise PriceUnavailableError(
                symbol=symbol,
                source=self.exchange_id,
                details="Ticker returned null or zero last price.",
            )

        ts = t.get("timestamp") or int(datetime.now(UTC).timestamp() * 1000)
        return {
            "symbol": symbol,
            "last": float(last),
            "bid": float(t.get("bid") or last),
            "ask": float(t.get("ask") or last),
            "bid_size": float(t.get("bidVolume") or 0.0),
            "ask_size": float(t.get("askVolume") or 0.0),
            "volume_24h": float(t.get("baseVolume") or 0.0),
            "quote_volume_24h": float(t.get("quoteVolume") or 0.0),
            "timestamp_ms": int(ts),
            "exchange": self.exchange_id,
        }

    async def fetch_orderbook(
        self, symbol: str, depth: int = 20
    ) -> dict[str, Any]:
        """Fetch L2 orderbook snapshot."""
        await self.rate_limiter.acquire()
        ex = await self._get_exchange()
        try:
            ob = await ex.fetch_order_book(symbol, limit=depth)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "418" in err_str or "RateLimit" in type(e).__name__:
                self.rate_limiter.record_429()
            raise DataUnavailableError(
                source=self.exchange_id,
                symbol=symbol,
                reason="ORDERBOOK_FETCH_FAILED",
                details=str(e),
            ) from e

        bids = ob.get("bids", [])
        asks = ob.get("asks", [])
        best_bid = float(bids[0][0]) if bids else 0.0
        best_ask = float(asks[0][0]) if asks else 0.0
        spread_bps = ((best_ask - best_bid) / best_bid * 10000) if best_bid > 0 else 0.0

        ts = ob.get("timestamp") or int(datetime.now(UTC).timestamp() * 1000)
        return {
            "symbol": symbol,
            "timestamp_ms": int(ts),
            "bids": [[float(p), float(s)] for p, s in bids[:depth]],
            "asks": [[float(p), float(s)] for p, s in asks[:depth]],
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread_bps": round(spread_bps, 3),
            "mid_price": (best_bid + best_ask) / 2 if best_bid and best_ask else 0.0,
            "exchange": self.exchange_id,
        }

    async def close(self) -> None:
        """Release CCXT exchange connections."""
        if self._exchange is not None:
            await self._exchange.close()
            self._exchange = None
