"""Regression tests — v2.0: Synthetic data fallback prevention.

These tests ensure that synthetic/fabricated data fallbacks are never
reintroduced in production code paths. Each test verifies a specific DEFECT fix.
"""

import pytest


# ─────────────────────────────────────────────────────────────────────────────
#  DEFECT-2 regression: broker must raise PriceUnavailableError, not return fake price
# ─────────────────────────────────────────────────────────────────────────────

class TestBrokerPriceUnavailable:
    """DEFECT-2: broker.get_latest_price() must raise PriceUnavailableError when no DB data."""

    @pytest.mark.asyncio
    async def test_get_latest_price_raises_when_no_candles(self, db_session):
        """Broker must raise PriceUnavailableError, never return a hard-coded fallback price."""
        from src.config.exceptions import PriceUnavailableError
        from src.paper.broker import PaperBroker

        broker = PaperBroker()
        with pytest.raises(PriceUnavailableError) as exc_info:
            await broker.get_latest_price(db_session, "NONEXISTENT_ASSET_XYZ")

        assert exc_info.value.reason == "PRICE_UNAVAILABLE"
        assert exc_info.value.symbol == "NONEXISTENT_ASSET_XYZ"

    @pytest.mark.asyncio
    async def test_get_latest_price_no_hardcoded_btc_fallback(self, db_session):
        """BTC price must not be returned from hard-coded dict when no candles exist."""
        from src.config.exceptions import PriceUnavailableError
        from src.paper.broker import PaperBroker

        broker = PaperBroker()
        with pytest.raises(PriceUnavailableError):
            price = await broker.get_latest_price(db_session, "BTC")
            pytest.fail(
                f"Expected PriceUnavailableError but got price={price}. "
                "Hard-coded price fallback has been re-introduced — DEFECT-2 regression!"
            )


# ─────────────────────────────────────────────────────────────────────────────
#  DEFECT-3 regression: DexScreener must raise on provider failure, not return mock
# ─────────────────────────────────────────────────────────────────────────────

class TestDexScreenerNoMockFallback:
    """DEFECT-3: DexScreenerProvider must raise ExternalProviderUnavailableError, not return mock pairs."""

    @pytest.mark.asyncio
    async def test_search_pairs_raises_on_network_failure(self):
        """Provider must raise ExternalProviderUnavailableError when unreachable."""
        import httpx

        from src.config.exceptions import ExternalProviderUnavailableError
        from src.ingestion.providers.dexscreener_provider import DexScreenerProvider

        provider = DexScreenerProvider(timeout_sec=0.001)  # tiny timeout to trigger failure

        # Force the client to raise on connection
        class FailClient:
            is_closed = False

            async def get(self, url, **kwargs):
                raise httpx.ConnectError("Simulated connection failure")

        provider._client = FailClient()  # type: ignore

        with pytest.raises(ExternalProviderUnavailableError) as exc_info:
            await provider.search_pairs("DOGE")

        assert exc_info.value.reason == "EXTERNAL_PROVIDER_UNAVAILABLE"

    def test_no_get_fallback_pairs_method_exists(self):
        """_get_fallback_pairs must not exist in DexScreenerProvider (removed in v2.0)."""
        from src.ingestion.providers.dexscreener_provider import DexScreenerProvider

        assert not hasattr(DexScreenerProvider, "_get_fallback_pairs"), (
            "_get_fallback_pairs() has been re-introduced! "
            "This method returned synthetic mock metrics — DEFECT-3 regression!"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  DEFECT-1 regression: ensure_seeded_data must not auto-generate synthetic candles
# ─────────────────────────────────────────────────────────────────────────────

class TestDashboardNoSyntheticCandles:
    """DEFECT-1: ensure_seeded_data() must not generate synthetic OHLCV candles."""

    def test_ensure_seeded_data_does_not_insert_ohlcv(self, monkeypatch):
        """After ensure_seeded_data(), no synthetic OHLCV candles should be in the DB."""
        from apps.dashboard.data_layer import DashboardDataLayer

        inserted_objects = []

        # We don't actually run the async function here, but inspect the source
        import inspect
        source = inspect.getsource(DashboardDataLayer.ensure_seeded_data)

        # Regression markers: these strings indicate synthetic candle generation
        forbidden_patterns = [
            "Generate synthetic",
            "base_ms",
            "trend_factor",
            "curr_p * 1.012",  # fake high calculation
            "64000.0",  # hard-coded BTC price
        ]
        for pattern in forbidden_patterns:
            assert pattern not in source, (
                f"Synthetic candle pattern '{pattern}' detected in ensure_seeded_data(). "
                "DEFECT-1 regression: synthetic candle generation has been re-introduced!"
            )

    def test_get_recent_alerts_no_hardcoded_alerts(self):
        """get_recent_alerts() must not return fabricated alert objects."""
        import inspect
        from apps.dashboard.data_layer import DashboardDataLayer

        source = inspect.getsource(DashboardDataLayer.get_recent_alerts)

        forbidden_patterns = [
            '"alert_1"',
            '"alert_2"',
            '"alert_3"',
            "SOL 24h momentum acceleration exceeded",
            "Bootstrap Model",
        ]
        for pattern in forbidden_patterns:
            assert pattern not in source, (
                f"Fabricated alert pattern '{pattern}' detected in get_recent_alerts(). "
                "DEFECT-4 regression: fake baseline alerts have been re-introduced!"
            )


# ─────────────────────────────────────────────────────────────────────────────
#  DEFECT-15 regression: idempotency key must exist on OrderSubmitRequest
# ─────────────────────────────────────────────────────────────────────────────

class TestOrderIdempotency:
    """DEFECT-15: OrderSubmitRequest must carry idempotency_key field."""

    def test_order_submit_request_has_idempotency_key(self):
        from src.paper.models import OrderSubmitRequest
        fields = OrderSubmitRequest.model_fields
        assert "idempotency_key" in fields, (
            "idempotency_key missing from OrderSubmitRequest — DEFECT-15 regression!"
        )

    def test_paper_order_db_model_has_idempotency_key(self):
        from src.database.models import PaperOrder
        cols = {c.name for c in PaperOrder.__table__.columns}
        assert "idempotency_key" in cols, (
            "idempotency_key column missing from paper_orders table — DEFECT-15 regression!"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  DEFECT-9 regression: CORS allow_origins must not be ["*"]
# ─────────────────────────────────────────────────────────────────────────────

class TestCORSNotWildcard:
    """DEFECT-9: API must not use allow_origins=['*'] with allow_credentials=True."""

    def test_cors_is_not_wildcard_with_credentials(self):
        import inspect
        from apps.api.main import create_app

        source = inspect.getsource(create_app)

        # v2.0 fix: CORS must use settings.cors_allowed_origins_list, not hardcoded ["*"]
        uses_settings_allowlist = "cors_allowed_origins_list" in source
        # v2.0 fix: allow_credentials must be False
        credentials_false = "allow_credentials=False" in source

        assert uses_settings_allowlist, (
            "DEFECT-9 regression: CORS is not using settings.cors_allowed_origins_list. "
            "Must use an explicit allow-list instead of allow_origins=['*']."
        )
        assert credentials_false, (
            "DEFECT-9 regression: allow_credentials must be False in v2.0. "
            "allow_credentials=True + wildcard origins is a security vulnerability."
        )


# ─────────────────────────────────────────────────────────────────────────────
#  DEFECT-7 regression: DataMode enum must exist
# ─────────────────────────────────────────────────────────────────────────────

class TestDataModeExists:
    """DEFECT-7: DataMode enum must be defined in constants."""

    def test_data_mode_enum_exists(self):
        from src.config.constants import DataMode

        assert "LIVE" in DataMode.__members__
        assert "HISTORICAL" in DataMode.__members__
        assert "SYNTHETIC_TEST" in DataMode.__members__

    def test_settings_has_data_mode(self):
        from src.config.settings import Settings
        fields = Settings.model_fields
        assert "DATA_MODE" in fields, "DATA_MODE missing from Settings — DEFECT-7 regression!"

    def test_live_trading_is_always_disabled(self):
        from src.config.settings import get_settings
        settings = get_settings()
        assert settings.LIVE_TRADING_ENABLED is False, (
            "LIVE_TRADING_ENABLED is True! This is not permitted in v2.0. "
            "Live trading is architecturally disabled."
        )


# ─────────────────────────────────────────────────────────────────────────────
#  DEFECT-6 regression: APP_VERSION must be 2.0.0
# ─────────────────────────────────────────────────────────────────────────────

class TestAppVersion:
    """DEFECT-6: APP_VERSION must be 2.0.0."""

    def test_app_version_is_2_0_0(self):
        from src.config.settings import get_settings
        settings = get_settings()
        assert settings.APP_VERSION == "2.0.0", (
            f"APP_VERSION={settings.APP_VERSION} is not '2.0.0' — DEFECT-6 regression!"
        )
