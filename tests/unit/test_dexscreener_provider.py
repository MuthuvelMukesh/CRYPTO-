"""Unit tests for DexScreener DEX liquidity provider."""

from datetime import UTC, datetime

import pytest

from src.ingestion.providers.dexscreener_provider import DexScreenerProvider


@pytest.mark.asyncio
async def test_dexscreener_parse_raw_pair() -> None:
    provider = DexScreenerProvider()

    raw_pair = {
        "chainId": "solana",
        "dexId": "raydium",
        "pairAddress": "sol_pepe_pair_123",
        "baseToken": {"symbol": "PEPE", "name": "Pepe"},
        "quoteToken": {"symbol": "USDC"},
        "priceUsd": "0.0000095",
        "liquidity": {"usd": 1250000.0},
        "volume": {"h24": 4500000.0, "h1": 250000.0, "m5": 25000.0},
        "priceChange": {"h24": 12.5, "h1": 2.1, "m5": 0.4},
        "txns": {"h24": {"buys": 1800, "sells": 1200}},
        "pairCreatedAt": int((datetime.now(UTC).timestamp() - (72 * 3600)) * 1000),  # 72 hours ago
    }

    parsed = provider._parse_pair(raw_pair)
    assert parsed.base_token_symbol == "PEPE"
    assert parsed.chain_id == "solana"
    assert parsed.liquidity_usd == 1250000.0
    assert parsed.volume_24h_usd == 4500000.0
    assert parsed.txns_24h_buys == 1800
    assert parsed.txns_24h_sells == 1200
    # buy ratio = 1800 / 3000 = 0.60
    assert pytest.approx(parsed.buy_pressure_ratio, rel=1e-2) == 0.60
    assert parsed.age_hours >= 70.0


@pytest.mark.asyncio
async def test_dexscreener_network_error_raises() -> None:
    """In v2.0, network failures must raise ExternalProviderUnavailableError."""
    from unittest.mock import patch

    from src.config.exceptions import ExternalProviderUnavailableError

    provider = DexScreenerProvider()
    with patch.object(provider.client, "get", side_effect=Exception("Connection refused")):
        with pytest.raises(ExternalProviderUnavailableError):
            await provider.search_pairs("DOGE")
