"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Crypto Intelligence Platform"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "production", "testing"] = "development"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    # Database
    # Default to local SQLite for immediate zero-config execution; easily overridden with PostgreSQL
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./crypto_intelligence.db",
        description="Async SQLAlchemy database connection string",
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Cache / Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for caching and token buckets",
    )
    CACHE_TTL_SECONDS: int = 300

    # API & Dashboard
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DASHBOARD_PORT: int = 8501

    # Ingestion & Timeframes
    DEFAULT_TIMEFRAME: str = "1h"
    SUPPORTED_TIMEFRAMES: str = "5m,15m,1h,4h,1d"
    PUBLIC_EXCHANGES: str = "binance,coinbase,kraken"
    RATE_LIMIT_CALLS_PER_MINUTE: int = 60

    # Paper Trading Defaults
    PAPER_INITIAL_CAPITAL: float = 100000.0
    MAKER_FEE_BPS: float = 2.0
    TAKER_FEE_BPS: float = 5.0
    DEFAULT_SLIPPAGE_BPS: float = 5.0
    LATENCY_MS: int = 50

    # Risk Limits
    MAX_PORTFOLIO_EXPOSURE_PCT: float = 80.0
    MAX_SINGLE_POSITION_PCT: float = 15.0
    MAX_MEME_EXPOSURE_PCT: float = 5.0
    MAX_SECTOR_EXPOSURE_PCT: float = 30.0
    MAX_DAILY_LOSS_PCT: float = 3.0
    MAX_DRAWDOWN_LIMIT_PCT: float = 15.0
    MAX_OPEN_POSITIONS: int = 12

    # Alerts
    ALERT_WEBHOOK_URL: str = ""
    ALERT_EMAIL_ENABLED: bool = False

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.DATABASE_URL.lower()

    @property
    def supported_timeframes_list(self) -> list[str]:
        return [tf.strip() for tf in self.SUPPORTED_TIMEFRAMES.split(",") if tf.strip()]

    @property
    def public_exchanges_list(self) -> list[str]:
        return [ex.strip() for ex in self.PUBLIC_EXCHANGES.split(",") if ex.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
