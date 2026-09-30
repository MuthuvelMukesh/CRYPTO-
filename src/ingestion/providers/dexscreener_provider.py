"""DexScreener public REST API data provider for DEX pools and meme tokens."""

from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from src.config.constants import DataQualityStatus
from src.utils.logging import get_logger

logger = get_logger("dexscreener_provider")


class DexPairMetrics(BaseModel):
    """Normalized metrics for a decentralized exchange liquidity pair."""

    model_config = ConfigDict(protected_namespaces=())

    chain_id: str
    dex_id: str
    pair_address: str
    base_token_symbol: str
    base_token_name: str
    quote_token_symbol: str
    price_usd: float
    liquidity_usd: float
    volume_24h_usd: float
    volume_1h_usd: float = 0.0
    volume_5m_usd: float = 0.0
    price_change_24h_pct: float = 0.0
    price_change_1h_pct: float = 0.0
    price_change_5m_pct: float = 0.0
    txns_24h_buys: int = 0
    txns_24h_sells: int = 0
    buy_pressure_ratio: float = 0.5  # buys / (buys + sells)
    pair_created_at: datetime | None = None
    age_hours: float = 999.0
    data_quality: DataQualityStatus = DataQualityStatus.GOOD
    fdv_usd: float | None = None
    market_cap_usd: float | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class DexScreenerProvider:
    """Client for querying DexScreener public open endpoints with graceful fallback."""

    BASE_URL = "https://api.dexscreener.com/latest/dex"

    def __init__(self, timeout_sec: float = 5.0) -> None:
        self.timeout_sec = timeout_sec
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout_sec)
        return self._client

    async def search_pairs(self, query: str) -> list[DexPairMetrics]:
        """Search DEX pairs matching a symbol or token address."""
        client = await self._get_client()
        url = f"{self.BASE_URL}/search?q={query}"
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                pairs = data.get("pairs") or []
                return [self._parse_pair(p) for p in pairs if p.get("liquidity", {}).get("usd")]
            logger.warning("dexscreener_search_failed", status_code=resp.status_code, query=query)
        except Exception as e:
            logger.warning("dexscreener_unreachable", query=query, error=str(e))

        # Fallback to deterministic mock metrics for demonstration & offline reliability
        return self._get_fallback_pairs(query)

    def _parse_pair(self, p: dict[str, Any]) -> DexPairMetrics:
        """Parse raw DexScreener JSON dict into normalized DexPairMetrics."""
        liq = float(p.get("liquidity", {}).get("usd") or 0.0)
        vol = p.get("volume") or {}
        v24 = float(vol.get("h24") or 0.0)
        v1 = float(vol.get("h1") or 0.0)
        v5m = float(vol.get("m5") or 0.0)

        changes = p.get("priceChange") or {}
        c24 = float(changes.get("h24") or 0.0)
        c1 = float(changes.get("h1") or 0.0)
        c5m = float(changes.get("m5") or 0.0)

        txns = p.get("txns", {}).get("h24") or {}
        buys = int(txns.get("buys") or 0)
        sells = int(txns.get("sells") or 0)
        tot_tx = buys + sells
        buy_ratio = (buys / tot_tx) if tot_tx > 0 else 0.5

        created_ms = p.get("pairCreatedAt")
        created_at = None
        age_hours = 999.0
        if created_ms:
            created_at = datetime.fromtimestamp(created_ms / 1000.0, tz=UTC)
            age_hours = max(0.1, (datetime.now(UTC) - created_at).total_seconds() / 3600.0)

        price = float(p.get("priceUsd") or 0.0)

        return DexPairMetrics(
            chain_id=p.get("chainId", "solana"),
            dex_id=p.get("dexId", "raydium"),
            pair_address=p.get("pairAddress", "unknown"),
            base_token_symbol=p.get("baseToken", {}).get("symbol", "UNKNOWN"),
            base_token_name=p.get("baseToken", {}).get("name", "Unknown"),
            quote_token_symbol=p.get("quoteToken", {}).get("symbol", "USDC"),
            price_usd=price,
            liquidity_usd=liq,
            volume_24h_usd=v24,
            volume_1h_usd=v1,
            volume_5m_usd=v5m,
            price_change_24h_pct=c24,
            price_change_1h_pct=c1,
            price_change_5m_pct=c5m,
            txns_24h_buys=buys,
            txns_24h_sells=sells,
            buy_pressure_ratio=round(buy_ratio, 3),
            pair_created_at=created_at,
            age_hours=round(age_hours, 1),
            fdv_usd=p.get("fdv"),
            market_cap_usd=p.get("marketCap"),
            data_quality=DataQualityStatus.GOOD,
            raw_payload=p,
        )

    def _get_fallback_pairs(self, query: str) -> list[DexPairMetrics]:
        """Generate high-fidelity fallback metrics for standard meme universe when offline."""
        mock_dex_map = {
            "DOGE": {"price": 0.125, "liq": 45000000.0, "v24": 125000000.0, "chain": "bsc", "dex": "pancakeswap", "age": 8500.0, "buys": 1420, "sells": 1150},
            "PEPE": {"price": 0.0000095, "liq": 18500000.0, "v24": 65000000.0, "chain": "ethereum", "dex": "uniswap", "age": 4200.0, "buys": 3200, "sells": 2100},
            "SHIB": {"price": 0.0000185, "liq": 24000000.0, "v24": 42000000.0, "chain": "ethereum", "dex": "uniswap", "age": 9500.0, "buys": 980, "sells": 920},
            "BONK": {"price": 0.0000215, "liq": 8500000.0, "v24": 28000000.0, "chain": "solana", "dex": "raydium", "age": 3100.0, "buys": 2150, "sells": 1640},
            "WIF": {"price": 2.15, "liq": 9200000.0, "v24": 35000000.0, "chain": "solana", "dex": "raydium", "age": 1800.0, "buys": 4100, "sells": 2900},
            "FLOKI": {"price": 0.000145, "liq": 6500000.0, "v24": 15000000.0, "chain": "bsc", "dex": "pancakeswap", "age": 5200.0, "buys": 890, "sells": 740},
        }
        sym = query.upper()
        info = mock_dex_map.get(sym, {
            "price": 0.05, "liq": 350000.0, "v24": 850000.0, "chain": "solana", "dex": "raydium", "age": 140.0, "buys": 420, "sells": 310,
        })
        buys = info["buys"]
        sells = info["sells"]
        buy_ratio = buys / (buys + sells)

        return [
            DexPairMetrics(
                chain_id=info["chain"],
                dex_id=info["dex"],
                pair_address=f"mock_pair_{sym.lower()}",
                base_token_symbol=sym,
                base_token_name=sym,
                quote_token_symbol="USDC",
                price_usd=info["price"],
                liquidity_usd=info["liq"],
                volume_24h_usd=info["v24"],
                volume_1h_usd=info["v24"] / 24.0,
                volume_5m_usd=info["v24"] / 288.0,
                price_change_24h_pct=5.5,
                price_change_1h_pct=1.2,
                price_change_5m_pct=0.3,
                txns_24h_buys=buys,
                txns_24h_sells=sells,
                buy_pressure_ratio=round(buy_ratio, 3),
                age_hours=info["age"],
                data_quality=DataQualityStatus.WARNING,
            )
        ]

    async def close(self) -> None:
        """Close underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
