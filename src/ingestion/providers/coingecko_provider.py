"""CoinGecko public market aggregator provider."""

import httpx
from pydantic import BaseModel

from src.utils.logging import get_logger

logger = get_logger("ingestion.coingecko")


class CoinGeckoMarketData(BaseModel):
    id: str
    symbol: str
    name: str
    current_price: float
    market_cap: float | None = None
    market_cap_rank: int | None = None
    fully_diluted_valuation: float | None = None
    total_volume_24h: float | None = None
    circulating_supply: float | None = None
    total_supply: float | None = None
    max_supply: float | None = None
    price_change_percentage_24h: float | None = None


class CoinGeckoProvider:
    """Public CoinGecko market API client with rate-limiting resilience."""

    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout = timeout_seconds
        self.client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=self.timeout)
        self._is_available = True

    @property
    def name(self) -> str:
        return "coingecko"

    @property
    def is_available(self) -> bool:
        return self._is_available

    async def fetch_markets(
        self,
        vs_currency: str = "usd",
        per_page: int = 50,
        page: int = 1,
    ) -> list[CoinGeckoMarketData]:
        """Fetch market overview with market cap, FDV, and supplies."""
        try:
            resp = await self.client.get(
                "/coins/markets",
                params={
                    "vs_currency": vs_currency,
                    "order": "market_cap_desc",
                    "per_page": per_page,
                    "page": page,
                    "sparkline": "false",
                },
            )
            if resp.status_code == 429:
                logger.warning("coingecko_rate_limited_429", status=429)
                self._is_available = False
                return []

            resp.raise_for_status()
            data = resp.json()
            self._is_available = True

            results: list[CoinGeckoMarketData] = []
            for item in data:
                results.append(
                    CoinGeckoMarketData(
                        id=item.get("id", ""),
                        symbol=item.get("symbol", "").upper(),
                        name=item.get("name", ""),
                        current_price=float(item.get("current_price") or 0.0),
                        market_cap=float(item["market_cap"]) if item.get("market_cap") is not None else None,
                        market_cap_rank=item.get("market_cap_rank"),
                        fully_diluted_valuation=(
                            float(item["fully_diluted_valuation"])
                            if item.get("fully_diluted_valuation") is not None
                            else None
                        ),
                        total_volume_24h=(
                            float(item["total_volume"])
                            if item.get("total_volume") is not None
                            else None
                        ),
                        circulating_supply=(
                            float(item["circulating_supply"])
                            if item.get("circulating_supply") is not None
                            else None
                        ),
                        total_supply=(
                            float(item["total_supply"])
                            if item.get("total_supply") is not None
                            else None
                        ),
                        max_supply=(
                            float(item["max_supply"])
                            if item.get("max_supply") is not None
                            else None
                        ),
                        price_change_percentage_24h=(
                            float(item["price_change_percentage_24h"])
                            if item.get("price_change_percentage_24h") is not None
                            else None
                        ),
                    )
                )
            return results
        except Exception as e:
            logger.warning("coingecko_fetch_markets_failed", error=str(e))
            self._is_available = False
            return []

    async def close(self) -> None:
        """Close HTTP client session."""
        await self.client.aclose()
