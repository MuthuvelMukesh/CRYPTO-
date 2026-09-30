"""Paper trading and virtual brokerage REST API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db
from src.paper.broker import PaperBroker
from src.paper.models import (
    OrderResponse,
    OrderSubmitRequest,
    PortfolioSummaryResponse,
    PositionResponse,
)

router = APIRouter(prefix="/api/v1/paper", tags=["Paper Trading"])
broker = PaperBroker()


class ResetAccountRequest(BaseModel):
    """Payload to reset virtual account."""

    account_id: str = Field(default="default_paper")
    starting_balance: float = Field(default=100000.0, ge=1000.0)


@router.get("/account", response_model=PortfolioSummaryResponse, summary="Get paper trading account summary")
async def get_paper_account(
    account_id: str = Query("default_paper", description="Virtual account identifier"),
    db: AsyncSession = Depends(get_db),
) -> PortfolioSummaryResponse:
    """Retrieve comprehensive marked-to-market portfolio summary and risk statistics."""
    return await broker.get_portfolio_summary(db, account_id=account_id)


@router.get("/positions", response_model=list[PositionResponse], summary="Get open paper positions")
async def get_paper_positions(
    account_id: str = Query("default_paper", description="Virtual account identifier"),
    db: AsyncSession = Depends(get_db),
) -> list[PositionResponse]:
    """Retrieve open positions with real-time mark-to-market valuations."""
    summary = await broker.get_portfolio_summary(db, account_id=account_id)
    return summary.open_positions


@router.post("/orders", response_model=OrderResponse, summary="Place a paper trading order")
async def place_paper_order(
    req: OrderSubmitRequest,
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """Submit a paper market or limit order with automated risk controls and micro-structure slippage."""
    try:
        return await broker.submit_order(db, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/positions/{symbol}/close", response_model=PositionResponse, summary="Close open paper position")
async def close_paper_position(
    symbol: str,
    account_id: str = Query("default_paper"),
    db: AsyncSession = Depends(get_db),
) -> PositionResponse:
    """Liquidate an open position completely at current market price."""
    try:
        return await broker.close_position(db, account_id=account_id, symbol=symbol)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/reset", summary="Reset virtual paper account")
async def reset_paper_account(
    req: ResetAccountRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Reset virtual account cash balance to initial capital and liquidate positions."""
    await broker.reset_account(db, account_id=req.account_id, starting_balance=req.starting_balance)
    return {"status": "SUCCESS", "message": f"Account '{req.account_id}' reset to ${req.starting_balance:,.2f}"}
