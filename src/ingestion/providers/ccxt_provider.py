"""CCXT exchange adapter using public APIs."""

import ccxt.async_support as ccxt_async

from src.config.constants import DataQualityStatus, Timeframe
from src.ingestion.providers.base import BaseDataProvider, RawCandle, RawTicker
from src.utils.logging import get_logger

logger = get_logger("ingestion.ccxt")


class CCXTProvider(BaseDataProvider):
    """Asynchronous CCXT provider communicating with public exchange endpoints."""

    def __init__(self, exchange_id: str = "binance"):
        self.exchange_id = exchange_id.lower()
        if not hasattr(ccxt_async, self.exchange_id):
            raise ValueError(f"Exchange '{exchange_id}' is not supported by CCXT.")

        exchange_class = getattr(ccxt_async, self.exchange_id)
        self.client: ccxt_async.Exchange = exchange_class({
            "enableRateLimit": True,
            "timeout": 15000,
        })
        self._is_available = True

    @property
    def name(self) -> str:
        return f"ccxt:{self.exchange_id}"

    @property
    def is_available(self) -> bool:
        return self._is_available

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: Timeframe = Timeframe.H1,
        since_ms: int | None = None,
        limit: int = 100,
    ) -> list[RawCandle]:
        """Fetch historical OHLCV candles from exchange."""
        try:
            raw_candles = await self.client.fetch_ohlcv(
                symbol=symbol,
                timeframe=str(timeframe.value),
                since=since_ms,
                limit=limit,
            )
            candles: list[RawCandle] = []
            for c in raw_candles:
                # c format: [timestamp, open, high, low, close, volume]
                candles.append(
                    RawCandle(
                        timestamp_ms=int(c[0]),
                        open=float(c[1]),
                        high=float(c[2]),
                        low=float(c[3]),
                        close=float(c[4]),
                        volume=float(c[5]) if c[5] is not None else 0.0,
                        validation_status=DataQualityStatus.GOOD,
                    )
                )
            self._is_available = True
            return candles
        except Exception as e:
            logger.warning(
                "ccxt_fetch_ohlcv_failed",
                exchange=self.exchange_id,
                symbol=symbol,
                error=str(e),
            )
            self._is_available = False
            return []

    async def fetch_ticker(self, symbol: str) -> RawTicker | None:
        """Fetch latest 24h ticker data."""
        try:
            ticker = await self.client.fetch_ticker(symbol)
            self._is_available = True
            return RawTicker(
                symbol=symbol,
                last_price=float(ticker.get("last") or ticker.get("close") or 0.0),
                bid=float(ticker.get("bid")) if ticker.get("bid") is not None else None,
                ask=float(ticker.get("ask")) if ticker.get("ask") is not None else None,
                volume_24h_usd=float(ticker.get("quoteVolume")) if ticker.get("quoteVolume") is not None else None,
                timestamp_ms=int(ticker.get("timestamp") or 0),
            )
        except Exception as e:
            logger.warning(
                "ccxt_fetch_ticker_failed",
                exchange=self.exchange_id,
                symbol=symbol,
                error=str(e),
            )
            self._is_available = False
            return None

    async def close(self) -> None:
        """Close exchange aiohttp session."""
        if self.client:
            await self.client.close()
            logger.info("ccxt_session_closed", exchange=self.exchange_id)
