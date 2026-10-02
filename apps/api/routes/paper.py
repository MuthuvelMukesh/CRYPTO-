"""Paper trading and virtual brokerage REST API endpoints — Platform v3.0.

Provides authenticated virtual execution, position tracking, audit reconciliation,
and paginated inspection for orders, fills, and ledger events.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.deps import AuthIdentity, get_current_auth, get_db
from src.config.exceptions import CryptoIntelligenceError, DuplicateOrderError
from src.database.models import LedgerEvent, PaperFill, PaperOrder
from src.paper.broker import PaperBroker
from src.paper.models import (
    OrderResponse,
    OrderSubmitRequest,
    PortfolioSummaryResponse,
    PositionResponse,
)
from src.paper.reconciliation import ReconciliationResult, reconcile_account_ledger

router = APIRouter(prefix="/api/v1/paper", tags=["Paper Trading"])
broker = PaperBroker()


class ResetAccountRequest(BaseModel):
    """Payload to reset virtual account."""

    account_id: str = Field(default="default_paper")
    starting_balance: float = Field(default=100000.0, ge=1000.0)


@router.get("/reconcile", response_model=ReconciliationResult, summary="Reconcile paper account against ledger")
async def reconcile_paper_account(
    account_id: str = Query("default_paper", description="Virtual account identifier"),
    auth: AuthIdentity = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> ReconciliationResult:
    """Audit account state by replaying all immutable ledger events from inception."""
    return await reconcile_account_ledger(db, account_id=account_id)


@router.get("/account", response_model=PortfolioSummaryResponse, summary="Get paper trading account summary")
async def get_paper_account(
    account_id: str = Query("default_paper", description="Virtual account identifier"),
    auth: AuthIdentity = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> PortfolioSummaryResponse:
    """Retrieve comprehensive marked-to-market portfolio summary and risk statistics."""
    return await broker.get_portfolio_summary(db, account_id=account_id)


@router.get("/positions", response_model=list[PositionResponse], summary="Get open paper positions")
async def get_paper_positions(
    account_id: str = Query("default_paper", description="Virtual account identifier"),
    auth: AuthIdentity = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> list[PositionResponse]:
    """Retrieve open positions with real-time mark-to-market valuations."""
    summary = await broker.get_portfolio_summary(db, account_id=account_id)
    return summary.open_positions


@router.get("/orders", summary="Get paginated history of paper trading orders")
async def list_paper_orders(
    account_id: str = Query("default_paper", description="Virtual account identifier"),
    status_filter: str | None = Query(default=None, alias="status", description="Filter by status (e.g. FILLED, PENDING)"),
    asset_id: str | None = Query(default=None, description="Filter by asset symbol/id"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth: AuthIdentity = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve paginated paper orders."""
    stmt = (
        select(PaperOrder)
        .options(selectinload(PaperOrder.fills))
        .where(PaperOrder.account_id == account_id)
        .order_by(desc(PaperOrder.created_at))
    )
    if status_filter:
        stmt = stmt.where(PaperOrder.status == status_filter.upper())
    if asset_id:
        stmt = stmt.where(PaperOrder.asset_id == asset_id.upper())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = (await db.execute(count_stmt)).scalar_one()

    res = await db.execute(stmt.offset(offset).limit(limit))
    orders = res.scalars().all()

    return {
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "orders": [
            {
                "id": o.id,
                "account_id": o.account_id,
                "asset_id": o.asset_id,
                "order_type": o.order_type,
                "side": o.side,
                "quantity": float(o.quantity),
                "limit_price": float(o.limit_price) if o.limit_price is not None else None,
                "stop_price": float(o.stop_price) if o.stop_price is not None else None,
                "status": o.status,
                "idempotency_key": o.idempotency_key,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "fills": [
                    {
                        "fill_id": f.id,
                        "time": f.time.isoformat() if f.time else None,
                        "fill_price": float(f.fill_price),
                        "quantity": float(f.quantity),
                        "fee_usd": float(f.fee_usd),
                        "slippage_usd": float(f.slippage_usd),
                    }
                    for f in o.fills
                ],
            }
            for o in orders
        ],
    }


@router.get("/fills", summary="Get paginated history of paper execution fills")
async def list_paper_fills(
    account_id: str = Query("default_paper", description="Virtual account identifier"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth: AuthIdentity = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve paginated paper execution fills."""
    stmt = (
        select(PaperFill)
        .join(PaperOrder, PaperFill.order_id == PaperOrder.id)
        .where(PaperOrder.account_id == account_id)
        .order_by(desc(PaperFill.time))
    )
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = (await db.execute(count_stmt)).scalar_one()

    res = await db.execute(stmt.offset(offset).limit(limit))
    fills = res.scalars().all()

    return {
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "fills": [
            {
                "id": f.id,
                "order_id": f.order_id,
                "time": f.time.isoformat() if f.time else None,
                "fill_price": float(f.fill_price),
                "quantity": float(f.quantity),
                "fee_usd": float(f.fee_usd),
                "slippage_usd": float(f.slippage_usd),
            }
            for f in fills
        ],
    }


@router.get("/ledger", summary="Get paginated immutable ledger audit events")
async def list_ledger_events(
    account_id: str = Query("default_paper", description="Virtual account identifier"),
    event_type: str | None = Query(default=None, description="Filter by event type"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth: AuthIdentity = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve immutable ledger event stream with server-side pagination."""
    stmt = (
        select(LedgerEvent)
        .where(LedgerEvent.account_id == account_id)
        .order_by(desc(LedgerEvent.created_at))
    )
    if event_type:
        stmt = stmt.where(LedgerEvent.event_type == event_type.upper())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = (await db.execute(count_stmt)).scalar_one()

    res = await db.execute(stmt.offset(offset).limit(limit))
    events = res.scalars().all()

    return {
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "account_id": e.account_id,
                "order_id": e.order_id,
                "asset_id": e.asset_id,
                "quantity": float(e.quantity) if e.quantity is not None else None,
                "price": float(e.price) if e.price is not None else None,
                "amount_usd": float(e.amount_usd) if e.amount_usd is not None else None,
                "cash_balance_after": float(e.cash_balance_after) if e.cash_balance_after is not None else None,
                "data_mode": e.data_mode,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
    }


@router.post("/orders", response_model=OrderResponse, summary="Place a paper trading order")
async def place_paper_order(
    req: OrderSubmitRequest,
    auth: AuthIdentity = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """Submit a paper market or limit order with automated risk controls and micro-structure slippage."""
    try:
        return await broker.submit_order(db, req)
    except DuplicateOrderError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except (ValueError, CryptoIntelligenceError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/positions/{symbol}/close", response_model=PositionResponse, summary="Close open paper position")
async def close_paper_position(
    symbol: str,
    account_id: str = Query("default_paper"),
    auth: AuthIdentity = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> PositionResponse:
    """Liquidate an open position completely at current market price."""
    try:
        return await broker.close_position(db, account_id=account_id, symbol=symbol)
    except (ValueError, CryptoIntelligenceError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/reset", summary="Reset virtual paper account")
async def reset_paper_account(
    req: ResetAccountRequest,
    auth: AuthIdentity = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Reset virtual account cash balance to initial capital and liquidate positions."""
    await broker.reset_account(db, account_id=req.account_id, starting_balance=req.starting_balance)
    return {"status": "SUCCESS", "message": f"Account '{req.account_id}' reset to ${req.starting_balance:,.2f}"}
