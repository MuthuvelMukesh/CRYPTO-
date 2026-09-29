"""Ingestion package exports."""

from src.ingestion.pipeline import (
    DEFAULT_UNIVERSE,
    ingest_market_ohlcv,
    seed_default_universe,
)
from src.ingestion.providers.base import BaseDataProvider, RawCandle, RawTicker
from src.ingestion.providers.ccxt_provider import CCXTProvider
from src.ingestion.providers.coingecko_provider import CoinGeckoProvider

__all__ = [
    "BaseDataProvider",
    "CCXTProvider",
    "CoinGeckoProvider",
    "DEFAULT_UNIVERSE",
    "RawCandle",
    "RawTicker",
    "ingest_market_ohlcv",
    "seed_default_universe",
]
