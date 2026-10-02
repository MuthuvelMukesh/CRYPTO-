"""Scanner API routes — Platform v3.0.

Exposes live factor scanner rankings using a single unified SQL query with window functions,
server-side pagination, filtering, sorting, data freshness tracking, and audit penalties.
"""

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import AuthIdentity, get_current_auth, get_db
from src.config.constants import HealthStatus
from src.config.settings import get_settings
from src.database.models import OHLCV, Asset, Feature, Market, ScannerSnapshot, Score

router = APIRouter(prefix="/api/v1/scanner", tags=["Live Scanner"])


class ScoreBreakdown(BaseModel):
    """Detailed multi-factor component breakdown."""

    opportunity: float | None = None
    quality: float | None = None
    risk: float | None = None
    trend: float | None = None
    momentum: float | None = None
    relative_strength: float | None = None
    liquidity: float | None = None
    factors: dict[str, Any] = Field(default_factory=dict)


class PenaltyItem(BaseModel):
    """Frictional or risk penalty deducted from raw ranking."""

    type: str
    penalty_pct: float
    reason: str


class ScannerRankingItem(BaseModel):
    """Comprehensive single-asset scanner ranking row."""

    model_config = ConfigDict(protected_namespaces=())

    rank: int
    asset_id: str
    symbol: str
    name: str
    asset_class: str
    primary_sector: str

    price: float | None = None
    price_age_seconds: float | None = None
    data_fresh: bool = False
    candle_time: str | None = None

    return_1d_pct: float | None = None
    return_7d_pct: float | None = None
    return_30d_pct: float | None = None

    opportunity_score: float | None = None
    score_breakdown: ScoreBreakdown
    penalties: list[PenaltyItem] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    model_type: str | None = None
    ranked_at: str | None = None
    partial_data: bool = False
    missing_inputs: list[str] = Field(default_factory=list)
    model_version: str | None = None


class ScannerRankingsResponse(BaseModel):
    """Paginated scanner rankings response."""

    model_config = ConfigDict(protected_namespaces=())

    data_mode: str
    scanner_status: str
    total_count: int
    limit: int
    offset: int
    fresh_count: int
    stale_count: int
    checked_at: str
    rankings: list[ScannerRankingItem]


@router.get(
    "/rankings",
    response_model=ScannerRankingsResponse,
    summary="Get scanner rankings via single-query aggregation with pagination & filtering",
)
async def get_scanner_rankings(
    auth: AuthIdentity = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sector: str | None = Query(default=None, description="Filter by primary sector (e.g. L1, DeFi)"),
    asset_class: str | None = Query(default=None, description="Filter by asset class (e.g. CORE, ALTCOIN)"),
    min_score: float | None = Query(default=None, description="Minimum opportunity score filter"),
    data_fresh_only: bool = Query(default=False, description="Filter only assets with fresh market data"),
    sort_by: str = Query(
        default="opportunity_score",
        description="Sort field: opportunity_score, price, return_1d, return_7d, return_30d, symbol",
    ),
    sort_order: Literal["asc", "desc"] = Query(default="desc", description="Sort direction"),
) -> ScannerRankingsResponse:
    """Retrieve scanner rankings using a single unified query with window functions.

    Guarantees O(1) constant database queries regardless of universe size,
    eliminating N+1 query performance degradation.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    stale_threshold = settings.SCANNER_STALE_THRESHOLD_SECONDS

    # 1. Window function subquery: latest Score per asset
    score_sub = (
        select(
            Score.asset_id,
            Score.opportunity_score,
            Score.quality_score,
            Score.risk_score,
            Score.trend_score,
            Score.momentum_score,
            Score.relative_strength_score,
            Score.liquidity_score,
            Score.risk_flags,
            Score.model_type,
            Score.breakdown_json,
            Score.time.label("score_time"),
            func.row_number().over(
                partition_by=Score.asset_id,
                order_by=desc(Score.time),
            ).label("rn"),
        ).subquery()
    )

    # 2. Window function subquery: latest Feature (1h) per asset
    feat_sub = (
        select(
            Feature.asset_id,
            Feature.return_1d,
            Feature.return_7d,
            Feature.return_30d,
            Feature.time.label("feat_time"),
            func.row_number().over(
                partition_by=Feature.asset_id,
                order_by=desc(Feature.time),
            ).label("rn"),
        )
        .where(Feature.timeframe == "1h")
        .subquery()
    )

    # 3. Window function subquery: latest OHLCV per market
    ohlcv_sub = (
        select(
            OHLCV.market_id,
            OHLCV.close,
            OHLCV.time.label("candle_time"),
            OHLCV.timeframe.label("candle_tf"),
            func.row_number().over(
                partition_by=OHLCV.market_id,
                order_by=desc(OHLCV.time),
            ).label("rn"),
        ).subquery()
    )

    # 4. Master single query
    base_stmt = (
        select(
            Asset.id.label("asset_id"),
            Asset.symbol,
            Asset.name,
            Asset.asset_class,
            Asset.primary_sector,
            score_sub.c.opportunity_score,
            score_sub.c.quality_score,
            score_sub.c.risk_score,
            score_sub.c.trend_score,
            score_sub.c.momentum_score,
            score_sub.c.relative_strength_score,
            score_sub.c.liquidity_score,
            score_sub.c.risk_flags,
            score_sub.c.model_type,
            score_sub.c.breakdown_json,
            score_sub.c.score_time,
            feat_sub.c.return_1d,
            feat_sub.c.return_7d,
            feat_sub.c.return_30d,
            feat_sub.c.feat_time,
            ohlcv_sub.c.close.label("latest_price"),
            ohlcv_sub.c.candle_time,
            ohlcv_sub.c.candle_tf,
        )
        .outerjoin(score_sub, (Asset.id == score_sub.c.asset_id) & (score_sub.c.rn == 1))
        .outerjoin(feat_sub, (Asset.id == feat_sub.c.asset_id) & (feat_sub.c.rn == 1))
        .outerjoin(Market, (Market.asset_id == Asset.id) & (Market.is_active.is_(True)))
        .outerjoin(ohlcv_sub, (ohlcv_sub.c.market_id == Market.id) & (ohlcv_sub.c.rn == 1))
    )

    # Apply filters
    if sector:
        base_stmt = base_stmt.where(func.lower(Asset.primary_sector) == sector.lower())
    if asset_class:
        base_stmt = base_stmt.where(func.lower(Asset.asset_class) == asset_class.lower())
    if min_score is not None:
        base_stmt = base_stmt.where(score_sub.c.opportunity_score >= min_score)

    # Dynamic sorting
    sort_column_map = {
        "opportunity_score": score_sub.c.opportunity_score,
        "price": ohlcv_sub.c.close,
        "return_1d": feat_sub.c.return_1d,
        "return_7d": feat_sub.c.return_7d,
        "return_30d": feat_sub.c.return_30d,
        "symbol": Asset.symbol,
    }
    col = sort_column_map.get(sort_by, score_sub.c.opportunity_score)
    order_clause = desc(col) if sort_order == "desc" else col.asc()
    base_stmt = base_stmt.order_by(order_clause)

    # Execute single aggregated query
    res = await db.execute(base_stmt)
    all_rows = res.all()

    # Post-process freshness, penalties, and build responses
    items: list[ScannerRankingItem] = []
    fresh_count = 0
    stale_count = 0

    tf_duration_map = {"5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}

    for row in all_rows:
        # Calculate freshness
        price = float(row.latest_price) if row.latest_price is not None else None
        age_seconds: float | None = None
        data_fresh = False
        candle_iso: str | None = None

        if row.candle_time is not None:
            ct = row.candle_time
            if ct.tzinfo is None:
                ct = ct.replace(tzinfo=UTC)
            age_seconds = round((now - ct).total_seconds(), 1)
            bar_duration = tf_duration_map.get(row.candle_tf, 3600)
            data_fresh = age_seconds <= (stale_threshold + bar_duration)
            candle_iso = ct.isoformat()

        if data_fresh:
            fresh_count += 1
        else:
            stale_count += 1

        if data_fresh_only and not data_fresh:
            continue

        # Penalties calculation
        penalties: list[PenaltyItem] = []
        if not data_fresh and price is not None:
            penalties.append(
                PenaltyItem(
                    type="STALE_MARKET_DATA",
                    penalty_pct=10.0,
                    reason=f"Market price is stale ({age_seconds}s old)",
                )
            )
        if row.liquidity_score is not None and row.liquidity_score < 30.0:
            penalties.append(
                PenaltyItem(
                    type="LOW_LIQUIDITY",
                    penalty_pct=15.0,
                    reason=f"Liquidity score is low ({row.liquidity_score:.1f}/100)",
                )
            )
        if row.risk_score is not None and row.risk_score > 70.0:
            penalties.append(
                PenaltyItem(
                    type="ELEVATED_RISK",
                    penalty_pct=20.0,
                    reason=f"Risk score is elevated ({row.risk_score:.1f}/100)",
                )
            )

        # Multi-factor score breakdown
        breakdown = ScoreBreakdown(
            opportunity=round(row.opportunity_score, 2) if row.opportunity_score is not None else None,
            quality=round(row.quality_score, 2) if row.quality_score is not None else None,
            risk=round(row.risk_score, 2) if row.risk_score is not None else None,
            trend=round(row.trend_score, 2) if row.trend_score is not None else None,
            momentum=round(row.momentum_score, 2) if row.momentum_score is not None else None,
            relative_strength=round(row.relative_strength_score, 2) if row.relative_strength_score is not None else None,
            liquidity=round(row.liquidity_score, 2) if row.liquidity_score is not None else None,
            factors=row.breakdown_json if isinstance(row.breakdown_json, dict) else {},
        )

        r1 = round(row.return_1d * 100.0, 2) if row.return_1d is not None else None
        r7 = round(row.return_7d * 100.0, 2) if row.return_7d is not None else None
        r30 = round(row.return_30d * 100.0, 2) if row.return_30d is not None else None

        bj = row.breakdown_json if isinstance(row.breakdown_json, dict) else {}
        items.append(
            ScannerRankingItem(
                rank=len(items) + 1,
                asset_id=row.asset_id,
                symbol=row.symbol,
                name=row.name,
                asset_class=row.asset_class,
                primary_sector=row.primary_sector,
                price=price,
                price_age_seconds=age_seconds,
                data_fresh=data_fresh,
                candle_time=candle_iso,
                return_1d_pct=r1,
                return_7d_pct=r7,
                return_30d_pct=r30,
                opportunity_score=round(row.opportunity_score, 2) if row.opportunity_score is not None else None,
                score_breakdown=breakdown,
                penalties=penalties,
                risk_flags=row.risk_flags or [],
                model_type=row.model_type,
                ranked_at=row.score_time.isoformat() if row.score_time else None,
                partial_data=bool(bj.get("_partial_data", False)),
                missing_inputs=list(bj.get("_missing_inputs", [])),
                model_version=str(bj.get("_model_version", "v3.0.0")) if bj.get("_model_version") else None,
            )
        )

    # Server-side pagination slicing
    total_count = len(items)
    paged_items = items[offset : offset + limit]

    scanner_status = (
        HealthStatus.DOWN.value
        if total_count == 0
        else (HealthStatus.STALE.value if stale_count > fresh_count else HealthStatus.UP.value)
    )

    return ScannerRankingsResponse(
        data_mode=settings.DATA_MODE.value,
        scanner_status=scanner_status,
        total_count=total_count,
        limit=limit,
        offset=offset,
        fresh_count=fresh_count,
        stale_count=stale_count,
        checked_at=now.isoformat(),
        rankings=paged_items,
    )


@router.get(
    "/status",
    summary="Scanner operational status and data freshness summary",
)
async def get_scanner_status(
    auth: AuthIdentity = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return scanner data mode, freshness, and operational state."""
    settings = get_settings()
    now = datetime.now(UTC)

    latest_res = await db.execute(select(OHLCV).order_by(desc(OHLCV.time)).limit(1))
    latest = latest_res.scalars().first()

    score_res = await db.execute(select(Score).limit(1))
    has_scores = score_res.scalar_one_or_none() is not None

    age_seconds = None
    data_status = HealthStatus.DOWN.value
    if latest:
        ct = latest.time
        if ct.tzinfo is None:
            ct = ct.replace(tzinfo=UTC)
        age_seconds = round((now - ct).total_seconds(), 1)
        data_status = (
            HealthStatus.UP.value
            if age_seconds <= settings.MARKET_DATA_STALE_THRESHOLD_SECONDS
            else HealthStatus.STALE.value
        )

    return {
        "data_mode": settings.DATA_MODE.value,
        "live_trading_enabled": settings.LIVE_TRADING_ENABLED,
        "market_data_status": data_status,
        "latest_candle_age_seconds": age_seconds,
        "has_scores": has_scores,
        "stale_threshold_seconds": settings.MARKET_DATA_STALE_THRESHOLD_SECONDS,
        "checked_at": now.isoformat(),
    }


@router.get(
    "/snapshots",
    summary="Historical scanner snapshot records with pagination & filtering",
)
async def get_scanner_snapshots(
    auth: AuthIdentity = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
    asset_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Return paginated historical scanner snapshot rows."""
    q = select(ScannerSnapshot).order_by(desc(ScannerSnapshot.snapshot_time))
    if asset_id:
        q = q.where(ScannerSnapshot.asset_id == asset_id.upper())

    # Count total
    count_q = select(func.count()).select_from(q.subquery())
    total_count = (await db.execute(count_q)).scalar_one()

    q = q.offset(offset).limit(limit)
    res = await db.execute(q)
    snaps = res.scalars().all()

    return {
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "snapshots": [
            {
                "id": s.id,
                "snapshot_time": s.snapshot_time.isoformat(),
                "asset_id": s.asset_id,
                "rank": s.rank,
                "opportunity_score": s.opportunity_score,
                "price_at_snapshot": s.price_at_snapshot,
                "data_fresh": s.data_fresh,
                "data_age_seconds": s.data_age_seconds,
                "data_mode": s.data_mode,
                "fwd_return_1h": s.fwd_return_1h,
                "fwd_return_24h": s.fwd_return_24h,
                "fwd_return_7d": s.fwd_return_7d,
            }
            for s in snaps
        ],
    }
