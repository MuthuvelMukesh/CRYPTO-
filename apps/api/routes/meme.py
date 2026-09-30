"""Meme Coin Radar and DEX intelligence REST API endpoints."""

from fastapi import APIRouter, HTTPException, Query, status

from src.scoring.meme_radar import MemeAuditRecord, MemeRadarEngine

router = APIRouter(prefix="/api/v1/meme", tags=["Meme Coin Radar"])
radar_engine = MemeRadarEngine()


@router.get("/radar", response_model=list[MemeAuditRecord], summary="Get ranked meme tokens and risk audits")
async def get_meme_radar(
    min_score: float = Query(0.0, ge=0.0, le=100.0, description="Minimum opportunity score filter"),
    max_risk_level: str | None = Query(None, description="Filter max risk (LOW, MODERATE, HIGH, CRITICAL)"),
) -> list[MemeAuditRecord]:
    """Retrieve ranked meme tokens with DEX liquidity depth, volume acceleration, and active risk deductions."""
    records = await radar_engine.scan_meme_tokens()

    if min_score > 0.0:
        records = [r for r in records if r.opportunity_score >= min_score]

    if max_risk_level:
        allowed = {"LOW": ["LOW"], "MODERATE": ["LOW", "MODERATE"], "HIGH": ["LOW", "MODERATE", "HIGH"]}.get(
            max_risk_level.upper(), ["LOW", "MODERATE", "HIGH", "CRITICAL"]
        )
        records = [r for r in records if r.risk_level in allowed]

    return records


@router.get("/{symbol}", response_model=MemeAuditRecord, summary="Get meme token deep-dive audit")
async def get_meme_detail(symbol: str) -> MemeAuditRecord:
    """Retrieve detailed DEX liquidity, holder distribution, and risk penalty card for a specific meme token."""
    records = await radar_engine.scan_meme_tokens(symbols=[symbol.upper()])
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meme token '{symbol}' not found on DEX liquidity aggregators",
        )
    return records[0]
