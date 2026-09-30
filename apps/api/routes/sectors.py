"""Crypto Sector Performance and Rotation REST API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db
from src.features.sector import SectorPerformance, get_all_sector_performances

router = APIRouter(prefix="/api/v1/sectors", tags=["Sectors & Rotation"])


@router.get("", response_model=list[SectorPerformance], summary="Get crypto sector rotation matrix")
async def list_sectors(
    rotation_status: str | None = Query(None, description="Filter by status: LEADING, ACCELERATING, WEAKENING, DECLINING"),
    db: AsyncSession = Depends(get_db),
) -> list[SectorPerformance]:
    """Retrieve performance, momentum acceleration, breadth, and rotation status across all crypto sectors."""
    sectors = await get_all_sector_performances(db)
    if rotation_status:
        sectors = [s for s in sectors if s.rotation_status.upper() == rotation_status.upper()]
    return sectors


@router.get("/{sector_name}", response_model=SectorPerformance, summary="Get single sector performance")
async def get_sector_detail(
    sector_name: str,
    db: AsyncSession = Depends(get_db),
) -> SectorPerformance:
    """Retrieve detailed performance and breadth for a specific sector."""
    sectors = await get_all_sector_performances(db)
    match = next((s for s in sectors if s.sector_name.lower() == sector_name.lower()), None)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sector '{sector_name}' not found",
        )
    return match
