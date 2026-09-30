"""v2.0 Exception hierarchy for data availability and integrity violations.

These exceptions replace all silent synthetic fallbacks in production paths.
Any code path that previously returned fake data should raise one of these instead.
"""


class CryptoIntelligenceError(Exception):
    """Base class for all platform errors."""


# ─────────────────────────────────────────────────────────────────────────────
#  Data availability errors — replace every silent synthetic fallback
# ─────────────────────────────────────────────────────────────────────────────

class DataUnavailableError(CryptoIntelligenceError):
    """Raised when a data source cannot supply the requested data.

    This must be used instead of returning fallback/synthetic values in any
    live or historical production code path.

    Example::

        raise DataUnavailableError(
            source="binance",
            symbol="SOL/USDT",
            reason="NO_RECENT_MARKET_DATA",
        )
    """

    def __init__(
        self,
        source: str,
        symbol: str | None = None,
        reason: str = "DATA_UNAVAILABLE",
        details: str | None = None,
    ) -> None:
        self.source = source
        self.symbol = symbol
        self.reason = reason
        self.details = details
        msg = f"[{reason}] source={source}"
        if symbol:
            msg += f" symbol={symbol}"
        if details:
            msg += f" — {details}"
        super().__init__(msg)


class PriceUnavailableError(DataUnavailableError):
    """Raised when no valid live or recent market price exists for an asset.

    The paper broker must raise this instead of using hard-coded fallback prices.
    """

    def __init__(self, symbol: str, source: str = "market_cache", details: str | None = None) -> None:
        super().__init__(
            source=source,
            symbol=symbol,
            reason="PRICE_UNAVAILABLE",
            details=details or (
                f"No validated market price found for {symbol}. "
                "Ensure market data ingestion is running."
            ),
        )


class InsufficientHistoricalDataError(CryptoIntelligenceError):
    """Raised when a backtest cannot proceed because historical data is missing.

    A backtest must NEVER fabricate candles. It must raise this error instead.
    """

    def __init__(
        self,
        missing_symbols: list[str] | None = None,
        missing_range_start: str | None = None,
        missing_range_end: str | None = None,
        reason: str = "INSUFFICIENT_HISTORICAL_DATA",
        details: str | None = None,
    ) -> None:
        self.missing_symbols = missing_symbols or []
        self.missing_range_start = missing_range_start
        self.missing_range_end = missing_range_end
        self.reason = reason
        msg_parts = [f"[{reason}]"]
        if missing_symbols:
            msg_parts.append(f"missing_symbols={missing_symbols}")
        if missing_range_start or missing_range_end:
            msg_parts.append(f"range=[{missing_range_start}..{missing_range_end}]")
        if details:
            msg_parts.append(details)
        super().__init__(" ".join(msg_parts))


class DataGapError(InsufficientHistoricalDataError):
    """Raised when required candle sequence has gaps exceeding configured tolerance."""

    def __init__(self, symbol: str, gap_start: str, gap_end: str) -> None:
        super().__init__(
            missing_symbols=[symbol],
            missing_range_start=gap_start,
            missing_range_end=gap_end,
            reason="DATA_GAP",
        )


class StaleDataError(DataUnavailableError):
    """Raised when data exists but is too old to use for live decisions."""

    def __init__(self, symbol: str, age_seconds: float, threshold_seconds: float, source: str) -> None:
        self.age_seconds = age_seconds
        self.threshold_seconds = threshold_seconds
        super().__init__(
            source=source,
            symbol=symbol,
            reason="STALE_DATA",
            details=f"Data is {age_seconds:.0f}s old, threshold={threshold_seconds}s",
        )


class ExternalProviderUnavailableError(DataUnavailableError):
    """Raised when an external API provider (DexScreener, CoinGecko, etc.) is unreachable.

    Must NOT be replaced by mock/fallback metrics in production code paths.
    """

    def __init__(self, provider: str, symbol: str | None = None, http_status: int | None = None) -> None:
        details = f"Provider={provider}"
        if http_status:
            details += f" HTTP={http_status}"
        super().__init__(
            source=provider,
            symbol=symbol,
            reason="EXTERNAL_PROVIDER_UNAVAILABLE",
            details=details,
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Order / execution errors
# ─────────────────────────────────────────────────────────────────────────────

class OrderRejectedError(CryptoIntelligenceError):
    """Raised when the risk engine rejects an order."""

    def __init__(self, reason_code: str, message: str, order_id: str | None = None) -> None:
        self.reason_code = reason_code
        self.order_id = order_id
        super().__init__(f"[ORDER_REJECTED:{reason_code}] {message}")


class DuplicateOrderError(OrderRejectedError):
    """Raised when idempotency check detects a duplicate order submission."""

    def __init__(self, idempotency_key: str) -> None:
        super().__init__(
            reason_code="DUPLICATE_ORDER",
            message=f"Order with idempotency_key={idempotency_key} already exists.",
        )


class LiveTradingDisabledError(CryptoIntelligenceError):
    """Raised if any code path attempts to invoke live exchange order submission.

    v2.0: LiveExecutionGateway is architecturally disabled.
    This exception provides an explicit barrier between demo and live paths.
    """

    def __init__(self) -> None:
        super().__init__(
            "LIVE_TRADING_DISABLED: v2.0 does not permit real-money order submission. "
            "LiveExecutionGateway is disabled by architecture. "
            "All orders are routed through PaperExecutionGateway only."
        )
