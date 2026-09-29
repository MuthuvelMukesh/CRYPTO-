"""Unit tests for exchange and aggregator data providers with error handling."""

from unittest.mock import AsyncMock, patch

import pytest

from src.config.constants import Timeframe
from src.ingestion.providers.ccxt_provider import CCXTProvider
from src.ingestion.providers.coingecko_provider import CoinGeckoProvider


@pytest.mark.asyncio
async def test_ccxt_provider_fetch_ohlcv_mock():
    """Verify CCXT provider parses OHLCV lists into RawCandle models."""
    provider = CCXTProvider(exchange_id="binance")

    # Mock raw CCXT response: [[timestamp, open, high, low, close, volume], ...]
    mock_data = [
        [1700000000000, 42000.0, 42500.0, 41800.0, 42300.0, 150.5],
        [1700003600000, 42300.0, 42800.0, 42100.0, 42600.0, 200.1],
    ]
    provider.client.fetch_ohlcv = AsyncMock(return_value=mock_data)

    candles = await provider.fetch_ohlcv("BTC/USDT", timeframe=Timeframe.H1)
    assert len(candles) == 2
    assert candles[0].open == 42000.0
    assert candles[0].close == 42300.0
    assert candles[1].volume == 200.1
    assert provider.is_available is True

    await provider.close()


@pytest.mark.asyncio
async def test_ccxt_provider_error_handling():
    """Verify CCXT provider catches network exceptions and enters degraded mode."""
    provider = CCXTProvider(exchange_id="binance")
    provider.client.fetch_ohlcv = AsyncMock(side_effect=Exception("Exchange network timeout"))

    candles = await provider.fetch_ohlcv("BTC/USDT", timeframe=Timeframe.H1)
    assert candles == []
    assert provider.is_available is False

    await provider.close()


@pytest.mark.asyncio
async def test_coingecko_provider_rate_limit_degradation():
    """Verify CoinGecko handles HTTP 429 gracefully without crashing."""
    provider = CoinGeckoProvider()

    mock_resp = AsyncMock()
    mock_resp.status_code = 429

    with patch.object(provider.client, "get", return_value=mock_resp):
        markets = await provider.fetch_markets()
        assert markets == []
        assert provider.is_available is False

    await provider.close()
