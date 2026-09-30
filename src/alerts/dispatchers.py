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


# Aliases for convenience
ConsoleAlertDispatcher = ConsoleDispatcher
DatabaseAlertDispatcher = DatabaseDispatcher

