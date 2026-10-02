"""MarketDataProvider Protocol + data transfer models — v2.0 adapter interface.

All exchange-specific implementations must implement the MarketDataProvider Protocol.
Exchange-specific code must NOT be spread throughout the project.
Only adapter modules under src/ingestion/providers/ may contain exchange specifics.

Also contains RawCandle and RawTicker for backward compatibility with the
validation layer and legacy ingestion pipeline.
"""

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from src.config.constants import DataQualityStatus

# ─────────────────────────────────────────────────────────────────────────────
#  Data Transfer Models (shared by all providers)
# ─────────────────────────────────────────────────────────────────────────────

class RawCandle(BaseModel):
    """Normalized OHLCV candle from any provider."""
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    validation_status: DataQualityStatus = DataQualityStatus.GOOD


# Alias used by live_ingestor.py
RawOHLCV = RawCandle


class RawTicker(BaseModel):
    """Normalized ticker from any provider."""
    symbol: str
    last: float
    bid: float = 0.0
    ask: float = 0.0
    volume_24h: float = 0.0
    quote_volume_24h: float = 0.0
    timestamp_ms: int = 0
    exchange: str = ""


# ─────────────────────────────────────────────────────────────────────────────
#  Provider Protocol
# ─────────────────────────────────────────────────────────────────────────────

@runtime_checkable
class MarketDataProvider(Protocol):
    """Abstract interface for all market data sources.

    Implementations:
    - CCXTProvider      — CCXT-backed (Binance, Coinbase, Kraken, etc.)
    - HistoricalProvider — reads stored DB candles, no live feed
    - SyntheticTestProvider — deterministic test data (only for TEST data mode)

    Selection is configuration-driven via settings.DEFAULT_EXCHANGE.
    """

    async def fetch_markets(self, exchange: str) -> list[dict[str, Any]]:
        """Return list of tradable markets from the exchange."""
        ...

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since_ms: int | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Fetch OHLCV candles from exchange.

        Raises DataUnavailableError if exchange is unreachable or returns no data.
        Never returns synthetic/fabricated candles.
        """
        ...

    async def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        """Fetch current ticker for a symbol.

        Raises PriceUnavailableError if exchange is unreachable.
        """
        ...

    async def fetch_orderbook(
        self, symbol: str, depth: int = 20
    ) -> dict[str, Any]:
        """Fetch current L2 orderbook snapshot."""
        ...

    async def close(self) -> None:
        """Release any connections or resources."""
        ...


# Backward-compat alias for code that still imports BaseDataProvider
BaseDataProvider = MarketDataProvider
