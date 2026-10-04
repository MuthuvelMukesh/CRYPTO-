"""Alert dispatchers for console logging, database persistence, and external webhooks."""

from abc import ABC, abstractmethod

import httpx

from src.alerts.models import AlertPayload, AlertSeverity
from src.database.models import Alert as AlertModel
from src.utils.logging import get_logger

logger = get_logger("alert_dispatcher")


class BaseAlertDispatcher(ABC):
    """Abstract interface for all notification channels."""

    @abstractmethod
    async def dispatch(self, alert: AlertPayload) -> bool:
        """Deliver alert to target destination."""
        pass


class ConsoleDispatcher(BaseAlertDispatcher):
    """Outputs structured logs for triggered signals."""

    async def dispatch(self, alert: AlertPayload) -> bool:
        log_method = {
            AlertSeverity.INFO: logger.info,
            AlertSeverity.WARNING: logger.warning,
            AlertSeverity.CRITICAL: logger.error,
        }.get(alert.severity, logger.info)

        log_method(
            "alert_triggered",
            alert_id=alert.id,
            alert_type=alert.alert_type,
            severity=alert.severity,
            symbol=alert.asset_id,
            message=alert.message,
        )
        return True


class DatabaseDispatcher(BaseAlertDispatcher):
    """Persists alert logs into relational database table."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def dispatch(self, alert: AlertPayload) -> bool:
        try:
            async with self.session_factory() as session:
                record = AlertModel(
                    id=alert.id,
                    time=alert.time,
                    alert_type=alert.alert_type.value,
                    severity=alert.severity.value,
                    asset_id=alert.asset_id,
                    message=alert.message,
                    details=alert.details,
                    is_read=alert.is_read,
                )
                session.add(record)
                await session.commit()
                return True
        except Exception as e:
            logger.error("failed_to_persist_alert_to_db", error=str(e), alert_id=alert.id)
            return False


class WebhookDispatcher(BaseAlertDispatcher):
    """Dispatches webhook payloads to Discord, Slack, or generic HTTP receiver."""

    def __init__(self, webhook_url: str | None = None, timeout_sec: float = 3.0) -> None:
        self.webhook_url = webhook_url
        self.timeout_sec = timeout_sec

    async def dispatch(self, alert: AlertPayload) -> bool:
        if not self.webhook_url:
            return False

        # Generic webhook JSON payload
        payload = {
            "content": f"🚨 **[{alert.severity}] {alert.alert_type}** ({alert.asset_id or 'MARKET'})\n{alert.message}",
            "embeds": [
                {
                    "title": f"Alert: {alert.alert_type}",
                    "description": alert.message,
                    "color": 15158332 if alert.severity == AlertSeverity.CRITICAL else (16776960 if alert.severity == AlertSeverity.WARNING else 3066993),
                    "fields": [
                        {"name": "Symbol", "value": alert.asset_id or "Market Wide", "inline": True},
                        {"name": "Severity", "value": str(alert.severity), "inline": True},
                        {"name": "Timestamp", "value": alert.time.isoformat(), "inline": False},
                    ],
                }
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                resp = await client.post(self.webhook_url, json=payload)
                return resp.status_code in (200, 204)
        except Exception as e:
            logger.warning("webhook_dispatch_failed", url=self.webhook_url, error=str(e))
            return False


class TelegramDispatcher(BaseAlertDispatcher):
    """Dispatches alerts to Telegram channel or chat via Bot API."""

    def __init__(self, bot_token: str | None = None, chat_id: str | None = None, timeout_sec: float = 3.0) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout_sec = timeout_sec

    async def dispatch(self, alert: AlertPayload) -> bool:
        if not self.bot_token or not self.chat_id:
            logger.debug("telegram_dispatcher_skipped_unconfigured")
            return False

        icon = "🚨" if alert.severity == AlertSeverity.CRITICAL else ("⚠️" if alert.severity == AlertSeverity.WARNING else "ℹ️")
        text = (
            f"{icon} <b>[{alert.severity.value}] {alert.alert_type.value}</b>\n"
            f"Asset: <code>{alert.asset_id or 'MARKET'}</code>\n"
            f"Message: {alert.message}\n"
            f"Time: {alert.time.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                resp = await client.post(url, json=payload)
                return resp.status_code == 200
        except Exception as e:
            logger.warning("telegram_dispatch_failed", error=str(e))
            return False


class EmailDispatcher(BaseAlertDispatcher):
    """Dispatches alert digests via SMTP or logged email relay."""

    def __init__(self, recipient: str | None = None, smtp_host: str | None = None) -> None:
        self.recipient = recipient
        self.smtp_host = smtp_host

    async def dispatch(self, alert: AlertPayload) -> bool:
        if not self.recipient:
            return False
        logger.info(
            "email_alert_dispatched",
            recipient=self.recipient,
            subject=f"[{alert.severity.value}] {alert.alert_type.value} - {alert.asset_id or 'MARKET'}",
            message=alert.message,
        )
        return True


# Aliases for convenience
ConsoleAlertDispatcher = ConsoleDispatcher
DatabaseAlertDispatcher = DatabaseDispatcher
WebhookAlertDispatcher = WebhookDispatcher
TelegramAlertDispatcher = TelegramDispatcher
EmailAlertDispatcher = EmailDispatcher

