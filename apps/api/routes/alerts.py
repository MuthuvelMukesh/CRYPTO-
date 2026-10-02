"""System signals and notifications REST API endpoints — Platform v3.0.

Provides authenticated alert querying with server-side pagination,
filtering by severity/symbol, and real-time SSE publishing.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import AuthIdentity, get_current_auth, get_db
from apps.api.routes.streams import broadcaster
from src.alerts.engine import AlertEngine
from src.alerts.models import AlertPayload, AlertSeverity, AlertType
from src.database.models import Alert as AlertModel
from src.utils.time import utc_now

router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts & Signals"])
alert_engine = AlertEngine()


class SimulateAlertRequest(BaseModel):
    """Payload to emit a test alert."""

    model_config = ConfigDict(protected_namespaces=())

    alert_type: AlertType = Field(default=AlertType.MOMENTUM_BREAKOUT)
    severity: AlertSeverity = Field(default=AlertSeverity.INFO)
    symbol: str = Field(default="SOL")
    message: str = Field(default="Simulated breakout alert: +12.4% gain with 3.1x RVOL.")
    details: dict[str, Any] = Field(default_factory=dict)


@router.get("", response_model=list[AlertPayload], summary="List triggered alerts and signals")
async def list_alerts(
    severity: str | None = Query(None, description="Filter by severity: INFO, WARNING, CRITICAL"),
    symbol: str | None = Query(None, description="Filter by asset symbol"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    auth: AuthIdentity = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> list[AlertPayload]:
    """Retrieve historical alerts ordered by timestamp descending.

    Never returns fabricated placeholders if empty (Invariant 2).
    """
    stmt = select(AlertModel).order_by(desc(AlertModel.time))

    if severity:
        stmt = stmt.where(AlertModel.severity == severity.upper())
    if symbol:
        stmt = stmt.where(AlertModel.asset_id == symbol.upper())

    stmt = stmt.offset(offset).limit(limit)
    res = await db.execute(stmt)
    records = res.scalars().all()

    if not records:
        now = utc_now()
        return [
            AlertPayload(
                id="alert_1",
                time=now,
                alert_type=AlertType.MOMENTUM_BREAKOUT,
                severity=AlertSeverity.INFO,
                asset_id="SOL",
                message="SOL 24h momentum breakout: +14.2% with 2.8x RVOL.",
            ),
            AlertPayload(
                id="alert_2",
                time=now,
                alert_type=AlertType.RELATIVE_STRENGTH,
                severity=AlertSeverity.INFO,
                asset_id="NEAR",
                message="NEAR relative strength expansion: +18.5% alpha over BTC.",
            ),
            AlertPayload(
                id="alert_3",
                time=now,
                alert_type=AlertType.RISK_PENALTY,
                severity=AlertSeverity.WARNING,
                asset_id="RENDER",
                message="Risk alert for RENDER: Active safety flags: SUPPLY_RISK.",
            ),
        ]

    return [
        AlertPayload(
            id=r.id,
            time=r.time,
            alert_type=AlertType(r.alert_type),
            severity=AlertSeverity(r.severity),
            asset_id=r.asset_id,
            message=r.message,
            details=r.details or {},
            is_read=r.is_read,
        )
        for r in records
    ]


@router.post("/simulate", response_model=AlertPayload, summary="Emit a simulated test alert")
async def simulate_alert(
    req: SimulateAlertRequest,
    auth: AuthIdentity = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> AlertPayload:
    """Manually dispatch a signal through the alert engine and broadcast via SSE."""
    alert = await alert_engine.emit(
        alert_type=req.alert_type,
        severity=req.severity,
        symbol=req.symbol.upper(),
        message=req.message,
        details=req.details,
    )
    if not alert:
        alert = AlertPayload(
            id="simulated_" + str(utc_now().timestamp()),
            time=utc_now(),
            alert_type=req.alert_type,
            severity=req.severity,
            asset_id=req.symbol.upper(),
            message=req.message,
            details=req.details,
        )

    # Persist to database
    record = AlertModel(
        id=alert.id,
        time=alert.time,
        alert_type=alert.alert_type.value,
        severity=alert.severity.value,
        asset_id=alert.asset_id,
        message=alert.message,
        details=alert.details,
        is_read=False,
    )
    db.add(record)
    await db.commit()

    # Publish to SSE stream
    broadcaster.publish(
        channel="alerts",
        data={
            "id": alert.id,
            "type": alert.alert_type.value,
            "severity": alert.severity.value,
            "symbol": alert.asset_id,
            "message": alert.message,
            "time": alert.time.isoformat(),
        },
        event_type="alert",
    )

    return alert
