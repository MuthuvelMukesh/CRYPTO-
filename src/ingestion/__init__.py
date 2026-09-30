"""Ingestion package exports — v2.0."""

from src.ingestion.pipeline import (
    DEFAULT_UNIVERSE,
    ingest_market_ohlcv,
    seed_default_universe,
)
from src.ingestion.providers.ccxt_provider import CCXTProvider
from src.ingestion.providers.coingecko_provider import CoinGeckoProvider
from src.ingestion.providers.dexscreener_provider import DexScreenerProvider

__all__ = [
    "CCXTProvider",
    "CoinGeckoProvider",
    "DexScreenerProvider",
    "DEFAULT_UNIVERSE",
    "ingest_market_ohlcv",
    "seed_default_universe",
]
