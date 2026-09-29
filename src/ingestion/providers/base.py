"""Abstract Base Data Provider Interface."""

from abc import ABC, abstractmethod

from pydantic import BaseModel

from src.config.constants import DataQualityStatus, Timeframe


class RawCandle(BaseModel):
    """Normalized raw candlestick payload."""
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float | None = None
    validation_status: DataQualityStatus = DataQualityStatus.GOOD


class RawTicker(BaseModel):
    """Normalized raw ticker quote."""
    symbol: str
    last_price: float
    bid: float | None = None
    ask: float | None = None
    volume_24h_usd: float | None = None
    timestamp_ms: int


class BaseDataProvider(ABC):
    """Abstract interface for all market and on-chain data providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Current operational status of provider."""
        pass

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: Timeframe = Timeframe.H1,
        since_ms: int | None = None,
        limit: int = 100,
    ) -> list[RawCandle]:
        """Fetch historical candlestick data."""
        pass

    @abstractmethod
    async def fetch_ticker(self, symbol: str) -> RawTicker | None:
        """Fetch latest 24h ticker quote."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Release underlying network sessions."""
        pass
