"""Virtual paper brokerage managing accounts, orders, positions, and portfolio accounting."""

import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backtesting.execution import ExecutionSimulator
from src.backtesting.models import OrderSide, SlippageModelType
from src.database.models import (
    OHLCV,
    Asset,
    PaperAccount,
    PaperEquity,
    PaperFill,
    PaperOrder,
    PaperPosition,
    PortfolioSnapshot,
)
from src.paper.models import (
    FillResponse,
    OrderResponse,
    OrderSubmitRequest,
    PaperOrderSide,
    PaperOrderStatus,
    PortfolioSummaryResponse,
    PositionResponse,
)
from src.paper.risk import RiskEngine
from src.utils.logging import get_logger
from src.utils.time import utc_now

logger = get_logger("paper_broker")


class PaperBroker:
    """Virtual broker executing simulated orders with micro-structure friction and portfolio accounting."""

    def __init__(self, risk_engine: RiskEngine | None = None) -> None:
        self.risk_engine = risk_engine or RiskEngine()
        self.simulator = ExecutionSimulator(
            maker_fee_bps=2.0,
            taker_fee_bps=5.0,
            slippage_model=SlippageModelType.MARKET_IMPACT,
            impact_gamma=0.1,
        )

    async def get_or_create_account(
        self,
        session: AsyncSession,
        account_id: str = "default_paper",
        name: str = "Primary Paper Portfolio",
        starting_balance: float = 100000.0,
    ) -> PaperAccount:
        """Fetch existing paper account or initialize a new virtual ledger."""
        stmt = select(PaperAccount).where(PaperAccount.id == account_id)
        res = await session.execute(stmt)
        account = res.scalars().first()

        if not account:
            account = PaperAccount(
                id=account_id,
                name=name,
                base_currency="USD",
                starting_balance=starting_balance,
                cash_balance=starting_balance,
                created_at=utc_now(),
            )
            session.add(account)
            await session.commit()
            logger.info("Initialized new paper trading account", account_id=account_id, balance=starting_balance)

        return account

    async def get_latest_price(self, session: AsyncSession, symbol: str) -> float:
        """Fetch latest market price for an asset symbol."""
        stmt = (
            select(OHLCV)
            .where(OHLCV.market_id.like(f"%{symbol.upper()}%"))
            .order_by(desc(OHLCV.time))
            .limit(1)
        )
        res = await session.execute(stmt)
        candle = res.scalars().first()
        if candle and candle.close > 0:
            return float(candle.close)

        # Robust fallbacks for baseline demonstration
        fallbacks = {
            "BTC": 64200.0,
            "ETH": 3450.0,
            "SOL": 154.20,
            "BNB": 595.0,
            "NEAR": 5.25,
            "RENDER": 6.50,
            "DOGE": 0.125,
            "PEPE": 0.0000095,
        }
        return fallbacks.get(symbol.upper(), 10.0)

    async def submit_order(
        self,
        session: AsyncSession,
        req: OrderSubmitRequest,
    ) -> OrderResponse:
        """Validate against risk rules and execute virtual paper order."""
        account = await self.get_or_create_account(session, req.account_id)

        # 1. Resolve Asset details
        asset_stmt = select(Asset).where(Asset.symbol == req.symbol.upper())
        asset_res = await session.execute(asset_stmt)
        asset = asset_res.scalars().first()
        asset_id = asset.id if asset else req.symbol.lower()
        asset_class = str(asset.asset_class.value) if asset and hasattr(asset.asset_class, "value") else "ALTCOIN"

        # 2. Get current market price
        market_price = req.limit_price or await self.get_latest_price(session, req.symbol)
        order_val_usd = req.quantity * market_price

        # 3. Retrieve open positions for risk validation
        pos_stmt = (
            select(PaperPosition)
            .where(PaperPosition.account_id == req.account_id, PaperPosition.is_open.is_(True))
        )
        open_pos_res = await session.execute(pos_stmt)
        open_positions = open_pos_res.scalars().all()

        open_pos_dicts = []
        invested_cap = 0.0
        for p in open_positions:
            curr_p = await self.get_latest_price(session, p.asset_id.upper())
            mkt_val = p.quantity * curr_p
            invested_cap += mkt_val
            open_pos_dicts.append({
                "symbol": p.asset_id.upper(),
                "asset_class": "MEME" if p.asset_id.upper() in {"DOGE", "PEPE", "SHIB", "BONK"} else "ALTCOIN",
                "market_value": mkt_val,
                "is_meme": p.asset_id.upper() in {"DOGE", "PEPE", "SHIB", "BONK"},
            })

        total_equity = account.cash_balance + invested_cap
        peak_equity = max(account.starting_balance, total_equity)
        current_dd_pct = ((peak_equity - total_equity) / peak_equity * 100.0) if peak_equity > 0 else 0.0

        # 4. Risk Inspection
        validation = self.risk_engine.validate_order(
            side=req.side,
            asset_symbol=req.symbol.upper(),
            asset_class=asset_class,
            order_value_usd=order_val_usd,
            cash_balance=account.cash_balance,
            total_equity=total_equity,
            open_positions=open_pos_dicts,
            current_drawdown_pct=current_dd_pct,
        )

        order_id = str(uuid.uuid4())
        now = utc_now()

        if not validation.passed:
            # Record Rejected Order
            rejected_order = PaperOrder(
                id=order_id,
                account_id=req.account_id,
                asset_id=asset_id,
                exchange_id="simulated",
                order_type=req.order_type.value,
                side=req.side.value,
                quantity=req.quantity,
                limit_price=req.limit_price,
                stop_price=req.stop_price,
                status=PaperOrderStatus.REJECTED.value,
                created_at=now,
                updated_at=now,
            )
            session.add(rejected_order)
            await session.commit()
            logger.warning("Order rejected by risk engine", reason=validation.reason, violations=validation.violations)
            raise ValueError(f"Order rejected by risk engine: {validation.reason}")

        # 5. Simulate Execution Friction
        exec_side = OrderSide.BUY if req.side == PaperOrderSide.BUY else OrderSide.SELL
        fill_price, _, slippage_usd, fee_usd = self.simulator.calculate_fill(
            side=exec_side,
            base_price=market_price,
            order_value_usd=order_val_usd,
            volume_24h_usd=2000000.0,
            is_maker=(req.order_type == "LIMIT"),
        )

        # 6. Record Filled Order and Fill
        paper_order = PaperOrder(
            id=order_id,
            account_id=req.account_id,
            asset_id=asset_id,
            exchange_id="simulated",
            order_type=req.order_type.value,
            side=req.side.value,
            quantity=req.quantity,
            limit_price=req.limit_price,
            stop_price=req.stop_price,
            status=PaperOrderStatus.FILLED.value,
            created_at=now,
            updated_at=now,
        )
        session.add(paper_order)

        fill_id = str(uuid.uuid4())
        fill_record = PaperFill(
            id=fill_id,
            order_id=order_id,
            time=now,
            fill_price=round(fill_price, 4),
            quantity=round(req.quantity, 6),
            fee_usd=round(fee_usd, 2),
            slippage_usd=round(slippage_usd, 2),
        )
        session.add(fill_record)

        # 7. Update Portfolio Ledger & Position Records
        target_pos_stmt = select(PaperPosition).where(
            PaperPosition.account_id == req.account_id,
            PaperPosition.asset_id == asset_id,
            PaperPosition.is_open.is_(True),
        )
        target_res = await session.execute(target_pos_stmt)
        existing_pos = target_res.scalars().first()

        if req.side == PaperOrderSide.BUY:
            # Deduct cash
            total_cash_outlay = (fill_price * req.quantity) + fee_usd
            account.cash_balance -= total_cash_outlay

            if existing_pos:
                # Average entry price update
                new_qty = existing_pos.quantity + req.quantity
                new_avg_entry = (
                    (existing_pos.quantity * existing_pos.avg_entry_price) + (req.quantity * fill_price)
                ) / new_qty
                existing_pos.quantity = new_qty
                existing_pos.avg_entry_price = new_avg_entry
                existing_pos.current_price = fill_price
                existing_pos.unrealized_pnl = (fill_price - new_avg_entry) * new_qty
            else:
                new_pos = PaperPosition(
                    id=str(uuid.uuid4()),
                    account_id=req.account_id,
                    asset_id=asset_id,
                    side="LONG",
                    quantity=req.quantity,
                    avg_entry_price=fill_price,
                    current_price=fill_price,
                    unrealized_pnl=0.0,
                    realized_pnl=0.0,
                    entry_time=now,
                    is_open=True,
                )
                session.add(new_pos)

        else:
            # SELL Order
            if not existing_pos:
                raise ValueError(f"Cannot sell: No open position found for {req.symbol}")

            qty_to_sell = min(req.quantity, existing_pos.quantity)
            gross_pnl = (fill_price - existing_pos.avg_entry_price) * qty_to_sell
            net_pnl = gross_pnl - fee_usd

            cash_inflow = (fill_price * qty_to_sell) - fee_usd
            account.cash_balance += cash_inflow

            existing_pos.realized_pnl += net_pnl

            if qty_to_sell >= existing_pos.quantity:
                # Complete liquidation
                existing_pos.quantity = 0.0
                existing_pos.is_open = False
                existing_pos.exit_time = now
                existing_pos.exit_reason = "USER_SELL"
                existing_pos.unrealized_pnl = 0.0
            else:
                # Partial reduction
                existing_pos.quantity -= qty_to_sell
                existing_pos.unrealized_pnl = (fill_price - existing_pos.avg_entry_price) * existing_pos.quantity

        await session.commit()
        logger.info(
            "Executed virtual paper order",
            order_id=order_id,
            symbol=req.symbol,
            side=req.side,
            qty=req.quantity,
            fill_price=fill_price,
        )

        return OrderResponse(
            id=order_id,
            account_id=req.account_id,
            symbol=req.symbol.upper(),
            side=req.side.value,
            order_type=req.order_type.value,
            quantity=req.quantity,
            status=PaperOrderStatus.FILLED.value,
            fills=[
                FillResponse(
                    id=fill_id,
                    order_id=order_id,
                    time=now.isoformat(),
                    fill_price=round(fill_price, 4),
                    quantity=round(req.quantity, 6),
                    fee_usd=round(fee_usd, 2),
                    slippage_usd=round(slippage_usd, 2),
                )
            ],
            created_at=now.isoformat(),
        )

    async def get_portfolio_summary(
        self,
        session: AsyncSession,
        account_id: str = "default_paper",
    ) -> PortfolioSummaryResponse:
        """Compute real-time mark-to-market valuations and risk statistics."""
        account = await self.get_or_create_account(session, account_id)

        pos_stmt = (
            select(PaperPosition)
            .where(PaperPosition.account_id == account_id, PaperPosition.is_open.is_(True))
        )
        pos_res = await session.execute(pos_stmt)
        open_positions = pos_res.scalars().all()

        position_responses: list[PositionResponse] = []
        invested_cap = 0.0
        total_unrealized_pnl = 0.0
        meme_val = 0.0
        max_single_val = 0.0

        for p in open_positions:
            curr_price = await self.get_latest_price(session, p.asset_id.upper())
            mkt_val = p.quantity * curr_price
            pnl_usd = (curr_price - p.avg_entry_price) * p.quantity
            pnl_pct = (pnl_usd / (p.quantity * p.avg_entry_price)) * 100.0 if (p.quantity * p.avg_entry_price) > 0 else 0.0

            invested_cap += mkt_val
            total_unrealized_pnl += pnl_usd
            max_single_val = max(max_single_val, mkt_val)

            if p.asset_id.upper() in {"DOGE", "PEPE", "SHIB", "BONK", "WIF"}:
                meme_val += mkt_val

            # Update DB current price and unrealized pnl
            p.current_price = curr_price
            p.unrealized_pnl = pnl_usd

            position_responses.append(
                PositionResponse(
                    id=p.id,
                    account_id=p.account_id,
                    symbol=p.asset_id.upper(),
                    side=p.side,
                    quantity=round(p.quantity, 6),
                    avg_entry_price=round(p.avg_entry_price, 4),
                    current_price=round(curr_price, 4),
                    market_value=round(mkt_val, 2),
                    unrealized_pnl=round(pnl_usd, 2),
                    unrealized_pnl_pct=round(pnl_pct, 2),
                    realized_pnl=round(p.realized_pnl, 2),
                    entry_time=p.entry_time.isoformat(),
                    exit_time=p.exit_time.isoformat() if p.exit_time else None,
                    is_open=p.is_open,
                    exit_reason=p.exit_reason,
                )
            )

        total_equity = account.cash_balance + invested_cap
        total_realized_pnl = sum(p.realized_pnl for p in open_positions)

        # Also sum realized pnl of closed positions
        closed_stmt = select(PaperPosition.realized_pnl).where(
            PaperPosition.account_id == account_id, PaperPosition.is_open.is_(False)
        )
        closed_res = await session.execute(closed_stmt)
        total_realized_pnl += sum(closed_res.scalars().all())

        total_pnl = total_unrealized_pnl + total_realized_pnl
        total_return_pct = ((total_equity - account.starting_balance) / account.starting_balance) * 100.0

        peak_equity = max(account.starting_balance, total_equity)
        drawdown_pct = ((peak_equity - total_equity) / peak_equity * 100.0) if peak_equity > 0 else 0.0

        meme_exposure_pct = (meme_val / total_equity * 100.0) if total_equity > 0 else 0.0
        max_single_position_pct = (max_single_val / total_equity * 100.0) if total_equity > 0 else 0.0

        now = utc_now()
        # Record periodic snapshot and equity curve
        session.add(
            PaperEquity(
                time=now,
                account_id=account_id,
                equity=round(total_equity, 2),
                cash=round(account.cash_balance, 2),
                invested_capital=round(invested_cap, 2),
                unrealized_pnl=round(total_unrealized_pnl, 2),
                realized_pnl=round(total_realized_pnl, 2),
                drawdown_pct=round(drawdown_pct, 2),
            )
        )
        session.add(
            PortfolioSnapshot(
                time=now,
                account_id=account_id,
                gross_exposure=round(invested_cap, 2),
                net_exposure=round(invested_cap, 2),
                meme_exposure_pct=round(meme_exposure_pct, 2),
                max_single_position_pct=round(max_single_position_pct, 2),
                positions_count=len(open_positions),
            )
        )
        await session.commit()

        return PortfolioSummaryResponse(
            account_id=account.id,
            name=account.name,
            base_currency=account.base_currency,
            starting_balance=round(account.starting_balance, 2),
            cash_balance=round(account.cash_balance, 2),
            invested_capital=round(invested_cap, 2),
            total_equity=round(total_equity, 2),
            unrealized_pnl=round(total_unrealized_pnl, 2),
            realized_pnl=round(total_realized_pnl, 2),
            total_pnl=round(total_pnl, 2),
            total_return_pct=round(total_return_pct, 2),
            drawdown_pct=round(drawdown_pct, 2),
            peak_equity=round(peak_equity, 2),
            gross_exposure=round(invested_cap, 2),
            net_exposure=round(invested_cap, 2),
            meme_exposure_pct=round(meme_exposure_pct, 2),
            max_single_position_pct=round(max_single_position_pct, 2),
            open_positions_count=len(open_positions),
            open_positions=position_responses,
            updated_at=now.isoformat(),
        )

    async def close_position(
        self,
        session: AsyncSession,
        account_id: str,
        symbol: str,
        reason: str = "MANUAL_CLOSE",
    ) -> PositionResponse:
        """Close an open position completely by issuing a synthetic sell order."""
        pos_stmt = select(PaperPosition).where(
            PaperPosition.account_id == account_id,
            PaperPosition.asset_id.ilike(symbol),
            PaperPosition.is_open.is_(True),
        )
        res = await session.execute(pos_stmt)
        pos = res.scalars().first()

        if not pos or pos.quantity <= 0:
            raise ValueError(f"No active open position found for {symbol}")

        qty_to_close = pos.quantity
        avg_entry = pos.avg_entry_price

        # Execute market sell
        order_req = OrderSubmitRequest(
            account_id=account_id,
            symbol=symbol.upper(),
            side=PaperOrderSide.SELL,
            quantity=qty_to_close,
        )
        order_res = await self.submit_order(session, order_req)

        # Refresh pos
        await session.refresh(pos)
        pos.exit_reason = reason
        await session.commit()

        curr_p = order_res.fills[0].fill_price if order_res.fills else pos.current_price
        cost_basis = avg_entry * qty_to_close
        pnl_pct = (pos.realized_pnl / cost_basis * 100.0) if cost_basis > 0 else 0.0

        return PositionResponse(
            id=pos.id,
            account_id=pos.account_id,
            symbol=pos.asset_id.upper(),
            side=pos.side,
            quantity=0.0,
            avg_entry_price=round(pos.avg_entry_price, 4),
            current_price=round(curr_p, 4),
            market_value=0.0,
            unrealized_pnl=0.0,
            unrealized_pnl_pct=round(pnl_pct, 2),
            realized_pnl=round(pos.realized_pnl, 2),
            entry_time=pos.entry_time.isoformat(),
            exit_time=pos.exit_time.isoformat() if pos.exit_time else utc_now().isoformat(),
            is_open=False,
            exit_reason=pos.exit_reason,
        )

    async def reset_account(
        self,
        session: AsyncSession,
        account_id: str = "default_paper",
        starting_balance: float = 100000.0,
    ) -> PaperAccount:
        """Reset paper account balance and liquidate all positions."""
        account = await self.get_or_create_account(session, account_id, starting_balance=starting_balance)
        account.starting_balance = starting_balance
        account.cash_balance = starting_balance

        # Mark all positions as closed
        pos_stmt = select(PaperPosition).where(
            PaperPosition.account_id == account_id,
            PaperPosition.is_open.is_(True),
        )
        res = await session.execute(pos_stmt)
        for p in res.scalars().all():
            p.is_open = False
            p.exit_time = utc_now()
            p.exit_reason = "ACCOUNT_RESET"

        await session.commit()
        logger.info("Reset paper trading account", account_id=account_id, balance=starting_balance)
        return account
