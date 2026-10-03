"""Unit tests for Alerting Engine, Dispatchers, and Cooldown Deduplication."""

import pytest

from src.alerts.dispatchers import ConsoleAlertDispatcher, DatabaseAlertDispatcher
from src.alerts.engine import AlertEngine
from src.alerts.models import AlertPayload, AlertSeverity, AlertType
from src.utils.time import utc_now


@pytest.mark.asyncio
async def test_console_alert_dispatcher() -> None:
    dispatcher = ConsoleAlertDispatcher()
    alert = AlertPayload(
        id="test_alert_1",
        time=utc_now(),
        alert_type=AlertType.MOMENTUM_BREAKOUT,
        severity=AlertSeverity.INFO,
        asset_id="SOL",
        message="SOL momentum breakout triggered.",
        details={"rvol": 3.2},
    )
    res = await dispatcher.dispatch(alert)
    assert res is True


@pytest.mark.asyncio
async def test_database_alert_dispatcher_without_session() -> None:
    dispatcher = DatabaseAlertDispatcher(session_factory=None)
    alert = AlertPayload(
        id="test_alert_2",
        time=utc_now(),
        alert_type=AlertType.RISK_PENALTY,
        severity=AlertSeverity.WARNING,
        asset_id="PEPE",
        message="Risk penalty threshold reached.",
    )
    res = await dispatcher.dispatch(alert)
    assert res is False


@pytest.mark.asyncio
async def test_alert_engine_deduplication_cooldown() -> None:
    engine = AlertEngine(cooldown_minutes=60)
    # First emit succeeds
    alert1 = await engine.emit(
        alert_type=AlertType.MOMENTUM_BREAKOUT,
        severity=AlertSeverity.INFO,
        symbol="BTC",
        message="BTC breaking out above 68,000.",
    )
    assert alert1 is not None
    assert alert1.asset_id == "BTC"
    assert alert1.alert_type == AlertType.MOMENTUM_BREAKOUT

    # Immediate second emit for same symbol and type is throttled (deduplicated)
    alert2 = await engine.emit(
        alert_type=AlertType.MOMENTUM_BREAKOUT,
        severity=AlertSeverity.INFO,
        symbol="BTC",
        message="BTC breaking out again.",
    )
    assert alert2 is None

    # Different alert type for same symbol succeeds
    alert3 = await engine.emit(
        alert_type=AlertType.REGIME_CHANGE,
        severity=AlertSeverity.WARNING,
        symbol="BTC",
        message="BTC regime shifted to High Volatility Bear.",
    )
    assert alert3 is not None
    assert alert3.alert_type == AlertType.REGIME_CHANGE


@pytest.mark.asyncio
async def test_telegram_and_email_dispatchers() -> None:
    from src.alerts.dispatchers import EmailAlertDispatcher, TelegramAlertDispatcher

    # Unconfigured Telegram returns False
    tg_unconfigured = TelegramAlertDispatcher(bot_token=None, chat_id=None)
    alert = AlertPayload(
        id="test_tg",
        time=utc_now(),
        alert_type=AlertType.MOMENTUM_BREAKOUT,
        severity=AlertSeverity.INFO,
        asset_id="SOL",
        message="SOL momentum breakout",
    )
    res_tg = await tg_unconfigured.dispatch(alert)
    assert res_tg is False

    # Email dispatcher dispatches successfully to recipient
    email = EmailAlertDispatcher(recipient="researcher@crypto.internal")
    res_email = await email.dispatch(alert)
    assert res_email is True


@pytest.mark.asyncio
async def test_alert_engine_quiet_hours_suppression() -> None:
    from datetime import datetime, UTC

    # Create engine with quiet hours enabled 00:00 to 23:59 (all day)
    engine = AlertEngine(
        cooldown_minutes=60,
        quiet_hours_enabled=True,
        quiet_hours_start="00:00",
        quiet_hours_end="23:59",
    )

    # INFO severity alert should be suppressed during quiet hours
    alert_info = await engine.emit(
        alert_type=AlertType.MOMENTUM_BREAKOUT,
        severity=AlertSeverity.INFO,
        symbol="ETH",
        message="ETH minor momentum breakout",
    )
    assert alert_info is None

    # CRITICAL severity alert bypasses quiet hours
    alert_crit = await engine.emit(
        alert_type=AlertType.REGIME_CHANGE,
        severity=AlertSeverity.CRITICAL,
        symbol="GLOBAL",
        message="Critical market-wide regime liquidation cascade!",
    )
    assert alert_crit is not None
    assert alert_crit.severity == AlertSeverity.CRITICAL
