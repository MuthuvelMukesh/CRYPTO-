"""Data models and enums for real-time market signals and risk alerts."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.utils.time import utc_now


class AlertSeverity(StrEnum):
    """Alert priority level."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertType(StrEnum):
    """Classification of signal or system event."""

    MOMENTUM_BREAKOUT = "MOMENTUM_BREAKOUT"
    RELATIVE_STRENGTH = "RELATIVE_STRENGTH"
    REGIME_CHANGE = "REGIME_CHANGE"
    RISK_PENALTY = "RISK_PENALTY"
    SECTOR_ROTATION = "SECTOR_ROTATION"
    ORDER_EXECUTION = "ORDER_EXECUTION"


class AlertPayload(BaseModel):
    """Normalized payload describing a triggered alert."""

    model_config = ConfigDict(protected_namespaces=())

    id: str
    time: datetime = Field(default_factory=utc_now)
    alert_type: AlertType
    severity: AlertSeverity = AlertSeverity.INFO
    asset_id: str | None = None
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    is_read: bool = False
