"""Real-time alerting engine evaluating market features, regime changes, and risk events."""

import uuid
from datetime import datetime, timedelta
from typing import Any

from src.alerts.dispatchers import BaseAlertDispatcher, ConsoleDispatcher
from src.alerts.models import AlertPayload, AlertSeverity, AlertType
from src.utils.logging import get_logger
from src.utils.time import utc_now

logger = get_logger("alert_engine")


class AlertEngine:
    """Evaluates quantitative conditions, deduplicates notifications, and dispatches to channels."""

    def __init__(
        self,
        dispatchers: list[BaseAlertDispatcher] | None = None,
        cooldown_minutes: int = 60,
    ) -> None:
        self.dispatchers: list[BaseAlertDispatcher] = dispatchers or [ConsoleDispatcher()]
        self.cooldown_minutes = cooldown_minutes
        self._recent_alerts: dict[tuple[str, str], datetime] = {}  # (symbol, alert_type) -> last_time

    def add_dispatcher(self, dispatcher: BaseAlertDispatcher) -> None:
        """Register a notification channel."""
        self.dispatchers.append(dispatcher)

    def _is_rate_limited(self, symbol: str, alert_type: AlertType, current_time: datetime) -> bool:
        """Check if an alert for this symbol and type was emitted within the cooldown window."""
        key = (symbol.upper(), alert_type.value)
        last_time = self._recent_alerts.get(key)
        if last_time and (current_time - last_time) < timedelta(minutes=self.cooldown_minutes):
            return True
        self._recent_alerts[key] = current_time
        return False

    async def emit(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        symbol: str | None,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> AlertPayload | None:
        """Deliver alert to all registered dispatchers if not rate-limited."""
        now = utc_now()
        target_sym = symbol or "GLOBAL"

        if self._is_rate_limited(target_sym, alert_type, now):
            logger.debug("alert_throttled", symbol=target_sym, alert_type=alert_type)
            return None

        payload = AlertPayload(
            id=str(uuid.uuid4()),
            time=now,
            alert_type=alert_type,
            severity=severity,
            asset_id=symbol,
            message=message,
            details=details or {},
        )

        for d in self.dispatchers:
            try:
                await d.dispatch(payload)
            except Exception as e:
                logger.error("dispatcher_error", dispatcher=type(d).__name__, error=str(e))

        return payload

    async def check_momentum_breakout(
        self,
        symbol: str,
        return_24h_pct: float,
        volume_to_20d_avg: float,
    ) -> AlertPayload | None:
        """Trigger alert if short-term returns expand with abnormal volume."""
        if return_24h_pct >= 8.0 and volume_to_20d_avg >= 2.0:
            msg = (
                f"{symbol} 24h momentum breakout: +{return_24h_pct:.2f}% gain "
                f"with abnormal volume ({volume_to_20d_avg:.1f}x 20-day average)."
            )
            return await self.emit(
                alert_type=AlertType.MOMENTUM_BREAKOUT,
                severity=AlertSeverity.INFO,
                symbol=symbol,
                message=msg,
                details={"return_24h_pct": return_24h_pct, "rvol_20": volume_to_20d_avg},
            )
        return None

    async def check_relative_strength(
        self,
        symbol: str,
        rs_btc_30d_pct: float,
    ) -> AlertPayload | None:
        """Trigger alert if asset significantly outperforms Bitcoin."""
        if rs_btc_30d_pct >= 15.0:
            msg = f"{symbol} relative strength expansion: +{rs_btc_30d_pct:.1f}% alpha over BTC over 30 days."
            return await self.emit(
                alert_type=AlertType.RELATIVE_STRENGTH,
                severity=AlertSeverity.INFO,
                symbol=symbol,
                message=msg,
                details={"rs_btc_30d_pct": rs_btc_30d_pct},
            )
        return None

    async def check_regime_change(
        self,
        old_regime: str,
        new_regime: str,
    ) -> AlertPayload | None:
        """Trigger alert when macro market regime changes state."""
        if old_regime != new_regime:
            sev = AlertSeverity.WARNING if new_regime == "RISK_OFF" else AlertSeverity.INFO
            msg = f"Macro Market Regime shift: {old_regime} ➔ {new_regime}. Portfolio exposure filters adjusted."
            return await self.emit(
                alert_type=AlertType.REGIME_CHANGE,
                severity=sev,
                symbol=None,
                message=msg,
                details={"old_regime": old_regime, "new_regime": new_regime},
            )
        return None

    async def check_risk_penalties(
        self,
        symbol: str,
        risk_flags: list[str],
    ) -> AlertPayload | None:
        """Trigger warning/critical alert if asset triggers safety flags."""
        critical_flags = {"VERY_NEW", "HIGH_CONCENTRATION", "LOW_LIQUIDITY", "SUPPLY_RISK"}
        active_critical = set(risk_flags) & critical_flags
        if active_critical:
            sev = AlertSeverity.CRITICAL if len(active_critical) >= 2 else AlertSeverity.WARNING
            msg = f"Risk alert for {symbol}: Active safety flags: {', '.join(active_critical)}."
            return await self.emit(
                alert_type=AlertType.RISK_PENALTY,
                severity=sev,
                symbol=symbol,
                message=msg,
                details={"risk_flags": list(active_critical)},
            )
        return None
