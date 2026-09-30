"""Scoring and quantitative scanner REST endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db
from src.config.constants import AssetClass, Timeframe
from src.database.models import Asset, Score
from src.scoring.engine import score_universe

router = APIRouter(prefix="/api/v1", tags=["Scoring & Scanner"])


class FactorContributionResponse(BaseModel):
    name: str
    score: float
    weight: float
    contribution: float


class PenaltyResponse(BaseModel):
    flag: str
    deduction: float
    reason: str


class ScoreSummaryResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    asset_id: str
    symbol: str
    name: str
    asset_class: str
    primary_sector: str
    model_type: str
    opportunity_score: float
    quality_score: float
    risk_score: float
    trend_score: float
    momentum_score: float
    relative_strength_score: float
    liquidity_score: float
    risk_flags: list[str]
    time: str


class ScoreDetailResponse(ScoreSummaryResponse):
    components: dict[str, FactorContributionResponse]
    penalties: list[PenaltyResponse]
    explainability_summary: str


@router.get("/scores", response_model=list[ScoreSummaryResponse], summary="Get ranked scores for all assets")
async def list_scores(
    asset_class: AssetClass | None = Query(None, description="Filter by asset class"),
    min_opportunity: float = Query(0.0, ge=0.0, le=100.0, description="Minimum opportunity score"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve latest explainable scores ranked by Opportunity Score."""
    query = (
        select(Score, Asset)
        .join(Asset, Score.asset_id == Asset.id)
        .where(Score.opportunity_score >= min_opportunity)
        .order_by(desc(Score.opportunity_score))
        .limit(limit)
    )

    if asset_class:
        query = query.where(Asset.asset_class == asset_class.value)

    res = await db.execute(query)
    rows = res.all()

    results: list[ScoreSummaryResponse] = []
    for score_obj, asset_obj in rows:
        results.append(
            ScoreSummaryResponse(
                asset_id=score_obj.asset_id,
                symbol=asset_obj.symbol,
                name=asset_obj.name,
                asset_class=asset_obj.asset_class,
                primary_sector=asset_obj.primary_sector,
                model_type=score_obj.model_type,
                opportunity_score=score_obj.opportunity_score,
                quality_score=score_obj.quality_score,
                risk_score=score_obj.risk_score,
                trend_score=score_obj.trend_score,
                momentum_score=score_obj.momentum_score,
                relative_strength_score=score_obj.relative_strength_score,
                liquidity_score=score_obj.liquidity_score,
                risk_flags=score_obj.risk_flags or [],
                time=score_obj.time.isoformat(),
            )
        )
    return results


@router.get("/scores/{symbol}", response_model=ScoreDetailResponse, summary="Get full score explainability card")
async def get_score_detail(
    symbol: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full factor breakdown and penalty itemization for a single asset."""
    query = (
        select(Score, Asset)
        .join(Asset, Score.asset_id == Asset.id)
        .where(Asset.symbol == symbol.upper())
        .order_by(desc(Score.time))
        .limit(1)
    )
    res = await db.execute(query)
    row = res.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Score record for symbol '{symbol.upper()}' not found.",
        )

    score_obj, asset_obj = row
    breakdown = score_obj.breakdown_json or {}

    components: dict[str, FactorContributionResponse] = {}
    for k, v in breakdown.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict):
            components[k] = FactorContributionResponse(
                name=v.get("name", k),
                score=float(v.get("score", 0.0)),
                weight=float(v.get("weight", 0.0)),
                contribution=float(v.get("contribution", 0.0)),
            )

    penalties_raw = breakdown.get("_penalties", [])
    penalties = [
        PenaltyResponse(
            flag=p.get("flag", ""),
            deduction=float(p.get("deduction", 0.0)),
            reason=p.get("reason", ""),
        )
        for p in penalties_raw
    ]

    return ScoreDetailResponse(
        asset_id=score_obj.asset_id,
        symbol=asset_obj.symbol,
        name=asset_obj.name,
        asset_class=asset_obj.asset_class,
        primary_sector=asset_obj.primary_sector,
        model_type=score_obj.model_type,
        opportunity_score=score_obj.opportunity_score,
        quality_score=score_obj.quality_score,
        risk_score=score_obj.risk_score,
        trend_score=score_obj.trend_score,
        momentum_score=score_obj.momentum_score,
        relative_strength_score=score_obj.relative_strength_score,
        liquidity_score=score_obj.liquidity_score,
        risk_flags=score_obj.risk_flags or [],
        time=score_obj.time.isoformat(),
        components=components,
        penalties=penalties,
        explainability_summary=breakdown.get("_summary", ""),
    )


@router.post("/scores/calculate", summary="Compute scores for entire active universe")
async def trigger_scoring(
    timeframe: Timeframe = Query(Timeframe.H1, description="Candlestick timeframe"),
    db: AsyncSession = Depends(get_db),
):
    """Trigger scoring calculation across all active assets."""
    cards = await score_universe(db, timeframe=timeframe)
    return {
        "status": "success",
        "scored_assets_count": len(cards),
        "top_ranked": [
            {"asset": c.asset_id, "model": c.model_type, "opportunity_score": c.opportunity_score}
            for c in cards[:5]
        ],
    }


@router.get("/scanner", response_model=list[ScoreSummaryResponse], summary="Market Scanner Filter")
async def scanner(
    asset_class: AssetClass | None = Query(None, description="Filter by class"),
    sector: str | None = Query(None, description="Filter by sector"),
    min_opportunity: float = Query(60.0, description="Minimum opportunity threshold"),
    max_risk_score: float | None = Query(None, description="Filter max risk"),
    exclude_flags: bool = Query(False, description="Exclude assets with active risk flags"),
    db: AsyncSession = Depends(get_db),
):
    """Multi-parameter quantitative scanner."""
    query = (
        select(Score, Asset)
        .join(Asset, Score.asset_id == Asset.id)
        .where(Score.opportunity_score >= min_opportunity)
        .order_by(desc(Score.opportunity_score))
    )

    if asset_class:
        query = query.where(Asset.asset_class == asset_class.value)
    if sector:
        query = query.where(Asset.primary_sector == sector)

    res = await db.execute(query)
    rows = res.all()

    results: list[ScoreSummaryResponse] = []
    for score_obj, asset_obj in rows:
        flags = score_obj.risk_flags or []
        if exclude_flags and len(flags) > 0:
            continue

        results.append(
            ScoreSummaryResponse(
                asset_id=score_obj.asset_id,
                symbol=asset_obj.symbol,
                name=asset_obj.name,
                asset_class=asset_obj.asset_class,
                primary_sector=asset_obj.primary_sector,
                model_type=score_obj.model_type,
                opportunity_score=score_obj.opportunity_score,
                quality_score=score_obj.quality_score,
                risk_score=score_obj.risk_score,
                trend_score=score_obj.trend_score,
                momentum_score=score_obj.momentum_score,
                relative_strength_score=score_obj.relative_strength_score,
                liquidity_score=score_obj.liquidity_score,
                risk_flags=flags,
                time=score_obj.time.isoformat(),
            )
        )
    return results
