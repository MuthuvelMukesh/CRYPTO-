"""Configuration management using Pydantic Settings — v2.0.0."""

from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ─────────────────────────────────────────────
#  Component version constants (reproducibility)
# ─────────────────────────────────────────────
APP_VERSION = "2.0.0"
SCHEMA_VERSION = "2.0.0"
FEATURE_VERSION = "2.0.0"
SCORING_VERSION = "2.0.0"
EXECUTION_MODEL_VERSION = "2.0.0"
UNIVERSE_VERSION = "2.0.0"
INGESTION_VERSION = "2.0.0"


class DataMode(StrEnum):
    """Controls which data source is active. Must be explicit — never inferred silently."""
    LIVE = "LIVE"
    HISTORICAL = "HISTORICAL"
    SYNTHETIC_TEST = "SYNTHETIC_TEST"
    REPLAY = "REPLAY"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "Crypto Intelligence Platform"
    APP_VERSION: str = APP_VERSION
    SCHEMA_VERSION: str = SCHEMA_VERSION
    FEATURE_VERSION: str = FEATURE_VERSION
    SCORING_VERSION: str = SCORING_VERSION
    EXECUTION_MODEL_VERSION: str = EXECUTION_MODEL_VERSION
    UNIVERSE_VERSION: str = UNIVERSE_VERSION
    INGESTION_VERSION: str = INGESTION_VERSION
    ENVIRONMENT: Literal["development", "production", "testing"] = "development"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    # ── Data Mode ────────────────────────────────────────────────────────────
    # LIVE        — real exchange market feeds
    # HISTORICAL  — database-backed historical data only
    # SYNTHETIC_TEST — explicitly generated test data; UI will show banner
    # REPLAY      — deterministic replay of stored event stream
    DATA_MODE: DataMode = DataMode.LIVE

    # ── Feature flags ────────────────────────────────────────────────────────
    MARKET_DATA_ENABLED: bool = True
    PAPER_TRADING_ENABLED: bool = True
    # v2.0: Live real-money trading is PERMANENTLY DISABLED by architecture.
    # Do not set this to True in any v2.x release.
    LIVE_TRADING_ENABLED: bool = False

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./crypto_intelligence.db",
        description="Async SQLAlchemy database connection string",
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ── Cache / Redis ─────────────────────────────────────────────────────────
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for ephemeral state (latest prices, heartbeats)",
    )
    # Redis keys for latest ticker/price: ephemeral only, not authoritative source
    REDIS_TICKER_TTL_SECONDS: int = 30
    REDIS_SCANNER_TTL_SECONDS: int = 60
    CACHE_TTL_SECONDS: int = 300

    # ── CORS (Security) ───────────────────────────────────────────────────────
    # Production: restrict to your dashboard domain(s)
    # Comma-separated list: "https://dashboard.example.com,http://localhost:8501"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:8501,http://127.0.0.1:8501"

    # ── Authentication & Security ─────────────────────────────────────────────
    SECRET_KEY: str = Field(
        default="dev-insecure-secret-key-change-in-production-min-32-chars",
        description="Secret key for JWT signature and CSRF tokens",
    )
    API_KEYS: str = Field(
        default="dev-api-key-researcher-1,dev-api-key-system",
        description="Comma-separated list of authorized API keys for programmatic access",
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    API_RATE_LIMIT_PER_MINUTE: int = 120
    CSRF_PROTECTION_ENABLED: bool = True

    # ── API & Dashboard ───────────────────────────────────────────────────────
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DASHBOARD_PORT: int = 8501

    # ── Market Data Ingestion ─────────────────────────────────────────────────
    DEFAULT_EXCHANGE: str = "binance"
    DEFAULT_TIMEFRAME: str = "1h"
    SUPPORTED_TIMEFRAMES: str = "5m,15m,1h,4h,1d"
    PUBLIC_EXCHANGES: str = "binance,coinbase,kraken"
    RATE_LIMIT_CALLS_PER_MINUTE: int = 60
    # Maximum age of market data before it is considered STALE (seconds)
    MARKET_DATA_STALE_THRESHOLD_SECONDS: int = 60
    # Maximum age before the scanner ranking itself is flagged STALE
    SCANNER_STALE_THRESHOLD_SECONDS: int = 120

    # ── Phase 3 Ingestion Hardening ──────────────────────────────────────────
    WS_HEARTBEAT_TIMEOUT: int = 30
    EXCHANGE_FAILOVER_COOLDOWN_SECONDS: int = 900  # 15 minutes
    EXCHANGE_FALLBACK_ORDER: str = "binance,coinbase,kraken"
    RATE_LIMIT_429_BACKOFF_SECONDS: int = 60

    # ── Paper Trading Defaults ────────────────────────────────────────────────
    PAPER_INITIAL_CAPITAL: float = 100_000.0
    MAKER_FEE_BPS: float = 2.0
    TAKER_FEE_BPS: float = 5.0
    DEFAULT_SLIPPAGE_BPS: float = 5.0
    LATENCY_MS: int = 50

    # ── Risk Limits ───────────────────────────────────────────────────────────
    MAX_PORTFOLIO_EXPOSURE_PCT: float = 80.0
    MAX_SINGLE_POSITION_PCT: float = 15.0
    MAX_MEME_EXPOSURE_PCT: float = 5.0
    MAX_SECTOR_EXPOSURE_PCT: float = 30.0
    MAX_DAILY_LOSS_PCT: float = 3.0
    MAX_DRAWDOWN_LIMIT_PCT: float = 15.0
    MAX_OPEN_POSITIONS: int = 12

    # ── Alerts ────────────────────────────────────────────────────────────────
    ALERT_WEBHOOK_URL: str = ""
    ALERT_EMAIL_ENABLED: bool = False

    # ── Dynamic Universe ──────────────────────────────────────────────────────
    # Minimum 24h USD volume for a market to qualify for the scanner universe
    UNIVERSE_MIN_VOLUME_24H_USD: float = 1_000_000.0
    # Minimum USD liquidity for market to be included
    UNIVERSE_MIN_LIQUIDITY_USD: float = 500_000.0
    # Maximum number of assets in the production scanner universe
    UNIVERSE_MAX_ASSETS: int = 200
    # Maximum seconds since last candle before asset is excluded as stale
    PRICE_STALE_THRESHOLD_SECONDS: int = 300

    @field_validator("LIVE_TRADING_ENABLED", mode="before")
    @classmethod
    def enforce_live_trading_disabled(cls, v: bool) -> bool:
        """v2.0 architectural constraint: live trading is always disabled."""
        if v is True:
            raise ValueError(
                "LIVE_TRADING_ENABLED=True is not permitted in v2.0. "
                "Live trading is architecturally disabled. "
                "Remove this setting to proceed."
            )
        return False

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.DATABASE_URL.lower()

    @property
    def is_synthetic_test_mode(self) -> bool:
        return self.DATA_MODE == DataMode.SYNTHETIC_TEST

    @property
    def supported_timeframes_list(self) -> list[str]:
        return [tf.strip() for tf in self.SUPPORTED_TIMEFRAMES.split(",") if tf.strip()]

    @property
    def public_exchanges_list(self) -> list[str]:
        return [ex.strip() for ex in self.PUBLIC_EXCHANGES.split(",") if ex.strip()]

    @property
    def exchange_fallback_order_list(self) -> list[str]:
        return [ex.strip() for ex in self.EXCHANGE_FALLBACK_ORDER.split(",") if ex.strip()]

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Fail fast in production if default or weak secrets are used."""
        if self.ENVIRONMENT == "production":
            weak_secrets = {
                "change-me",
                "dev-secret",
                "secret",
                "dev-insecure-secret-key-change-in-production-min-32-chars",
                "",
            }
            if self.SECRET_KEY in weak_secrets or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "Insecure or default SECRET_KEY in production environment. "
                    "Must be set to a cryptographically secure string of at least 32 characters."
                )
        return self

    @property
    def api_keys_list(self) -> list[str]:
        return [k.strip() for k in self.API_KEYS.split(",") if k.strip()]

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()

