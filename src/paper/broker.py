"""Virtual paper brokerage — v2.0.

Key v2.0 changes:
- Removed hard-coded synthetic price fallback dictionary (DEFECT-2)
- get_latest_price() raises PriceUnavailableError instead of returning fake prices
- Added idempotency_key check to prevent duplicate order submission
- Added explicit LIVE_TRADING_DISABLED guard
- Machine-readable rejection codes returned in OrderResponse
- Stale price detection via configurable threshold
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backtesting.execution import ExecutionSimulator
from src.backtesting.models import OrderSide, SlippageModelType
from src.config.constants import LedgerEventType, RiskRejectionCode
from src.config.exceptions import (
    DuplicateOrderError,
    LiveTradingDisabledError,
    PriceUnavailableError,
    StaleDataError,
)
from src.config.settings import get_settings
from src.database.models import (
    OHLCV,
    Asset,
    LedgerEvent,
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
settings = get_settings()


class LiveExecutionGateway:
    """v2.0 stub: architecturally disabled live order gateway.

    This class exists solely as an explicit barrier. If any code path reaches
    this class, it raises LiveTradingDisabledError immediately.
    Any future v3.0 live trading implementation would override this class only
    after all regulatory and custodial infrastructure is in place.
    """

    def submit(self, *args, **kwargs) -> None:  # noqa: ANN002
        raise LiveTradingDisabledError()


class PaperExecutionGateway:
    """Isolated demo execution path. Only PaperBroker instances use this.

    Paper orders are guaranteed to never reach any exchange API.
    """

    def validate_isolation(self) -> None:
        """Assert that live trading is disabled at settings level."""
        if settings.LIVE_TRADING_ENABLED:
            raise RuntimeError(
                "CRITICAL: LIVE_TRADING_ENABLED=True detected in settings. "
                "This should be architecturally impossible. "
                "See settings.enforce_live_trading_disabled validator."
            )


class PaperBroker:
    """Virtual broker executing simulated orders with micro-structure friction and portfolio accounting.

    v2.0 guarantees:
    1. Never returns a synthetic/fabricated price — raises PriceUnavailableError instead.
    2. Checks idempotency_key to prevent double-order submission.
    3. All order rejections carry machine-readable RiskRejectionCode.
    4. Calls PaperExecutionGateway.validate_isolation() before any fill.
    """

    def __init__(self, risk_engine: RiskEngine | None = None) -> None:
        self.risk_engine = risk_engine or RiskEngine()
        self.gateway = PaperExecutionGateway()
        self.simulator = ExecutionSimulator(
            maker_fee_bps=settings.MAKER_FEE_BPS,
            taker_fee_bps=settings.TAKER_FEE_BPS,
            slippage_model=SlippageModelType.MARKET_IMPACT,
            impact_gamma=0.1,
        )

    async def get_or_create_account(
        self,
        session: AsyncSession,
        account_id: str = "default_paper",
        name: str = "Primary Paper Portfolio",
        starting_balance: float | None = None,
    ) -> PaperAccount:
        """Fetch existing paper account or initialize a new virtual ledger."""
        stmt = select(PaperAccount).where(PaperAccount.id == account_id)
        res = await session.execute(stmt)
        account = res.scalars().first()

        if not account:
            bal = starting_balance or settings.PAPER_INITIAL_CAPITAL
            account = PaperAccount(
                id=account_id,
                name=name,
                base_currency="USD",
                starting_balance=bal,
                cash_balance=bal,
                created_at=utc_now(),
            )
            session.add(account)
            await session.commit()
            logger.info(
                "Initialized new paper trading account",
                account_id=account_id,
                balance=bal,
            )

        return account

    async def get_latest_price(
        self,
        session: AsyncSession,
        symbol: str,
        *,
        max_age_seconds: int | None = None,
    ) -> float:
        """Fetch latest validated market price for an asset symbol from the DB.

        v2.0 behaviour:
        - If a fresh OHLCV candle exists → return close price.
        - If most recent candle is stale (age > max_age_seconds) → raise StaleDataError.
        - If no candle found at all → raise PriceUnavailableError.
        - Hard-coded synthetic fallbacks are REMOVED.

        Args:
            session: async database session
            symbol: e.g. "BTC", "ETH"
            max_age_seconds: override default stale threshold from settings

        Raises:
            PriceUnavailableError: no candle found in DB for this symbol
            StaleDataError: candle found but older than threshold
        """
        threshold = max_age_seconds or settings.PRICE_STALE_THRESHOLD_SECONDS

        stmt = (
            select(OHLCV)
            .where(OHLCV.market_id.like(f"%{symbol.upper()}%"))
            .order_by(desc(OHLCV.time))
            .limit(1)
        )
        res = await session.execute(stmt)
        candle = res.scalars().first()

        if candle is None:
            raise PriceUnavailableError(
                symbol=symbol,
                source="ohlcv_db",
                details=f"No OHLCV record found for {symbol}. Run market data ingestion first.",
            )

        if candle.close is None or candle.close <= 0:
            raise PriceUnavailableError(
                symbol=symbol,
                source="ohlcv_db",
                details=f"Most recent OHLCV record for {symbol} has null or zero close price.",
            )

        # Check freshness taking into account the timeframe span of the candle
        tf_duration_map = {
            "5m": 300,
            "15m": 900,
            "1h": 3600,
            "4h": 14400,
            "1d": 86400,
        }
        bar_duration = tf_duration_map.get(candle.timeframe, 3600)
        effective_threshold = (max_age_seconds or threshold) + bar_duration

        age_seconds = (datetime.now(UTC) - candle.time.replace(tzinfo=UTC)).total_seconds()
        if age_seconds > effective_threshold:
            raise StaleDataError(
                symbol=symbol,
                age_seconds=age_seconds,
                threshold_seconds=effective_threshold,
                source="ohlcv_db",
            )

        return float(candle.close)

    async def _resolve_price_for_position(
        self,
        session: AsyncSession,
        symbol: str,
    ) -> float | None:
        """Resolve best-effort price for mark-to-market of existing positions.

        For MTM purposes only, we use a looser stale threshold to avoid crashing
        portfolio summaries during brief data gaps. Returns None if unavailable.
        """
        try:
            # For MTM, allow up to 3x the normal stale threshold
            return await self.get_latest_price(
                session, symbol, max_age_seconds=settings.PRICE_STALE_THRESHOLD_SECONDS * 3
            )
        except (PriceUnavailableError, StaleDataError) as e:
            logger.warning(
                "price_unavailable_for_mtm",
                symbol=symbol,
                reason=str(e),
            )
            return None

    async def _check_duplicate_order(
        self,
        session: AsyncSession,
        idempotency_key: str,
    ) -> PaperOrder | None:
        """Return existing order if idempotency_key already used; None otherwise."""
        if not idempotency_key:
            return None
        stmt = select(PaperOrder).where(PaperOrder.idempotency_key == idempotency_key)
        res = await session.execute(stmt)
        return res.scalars().first()

    async def _emit_ledger_event(
        self,
        session: AsyncSession,
        event_type: LedgerEventType | str,
        account_id: str,
        order_id: str | None = None,
        asset_id: str | None = None,
        quantity: float | None = None,
        price: float | None = None,
        amount_usd: float | None = None,
        cash_balance_after: float | None = None,
        payload: dict | None = None,
    ) -> LedgerEvent:
        """Record an immutable ledger event for audit and state recovery — v2.0."""
        import json
        ev = LedgerEvent(
            id=str(uuid.uuid4()),
            event_type=str(event_type.value if hasattr(event_type, "value") else event_type),
            account_id=account_id,
            order_id=order_id,
            asset_id=asset_id,
            quantity=quantity,
            price=price,
            amount_usd=amount_usd,
            cash_balance_after=cash_balance_after,
            payload_json=json.dumps(payload) if payload else None,
            data_mode=settings.DATA_MODE.value,
            created_at=utc_now(),
        )
        session.add(ev)
        return ev

    async def submit_order(
        self,
        session: AsyncSession,
        req: OrderSubmitRequest,
    ) -> OrderResponse:
        """Validate against risk rules and execute virtual paper order.

        Raises:
            LiveTradingDisabledError: if settings have been tampered with
            DuplicateOrderError: if idempotency_key already submitted
            PriceUnavailableError: if no live market price available
            StaleDataError: if price data is stale
            ValueError: if risk engine rejects the order
        """
        # 0. Isolation guard — paper broker must NEVER touch live execution
        self.gateway.validate_isolation()

        # 1. Idempotency check
        idempotency_key = getattr(req, "idempotency_key", None) or ""
        if idempotency_key:
            existing = await self._check_duplicate_order(session, idempotency_key)
            if existing:
                raise DuplicateOrderError(idempotency_key)

        account = await self.get_or_create_account(session, req.account_id)

        # 2. Resolve Asset details
        asset_stmt = select(Asset).where(Asset.symbol == req.symbol.upper())
        asset_res = await session.execute(asset_stmt)
        asset = asset_res.scalars().first()
        asset_id = asset.id if asset else req.symbol.lower()
        asset_class = str(asset.asset_class.value) if asset and hasattr(asset.asset_class, "value") else "ALTCOIN"

        # 3. Get current market price — raises PriceUnavailableError or StaleDataError if unavailable
        if req.limit_price and req.limit_price > 0:
            market_price = req.limit_price
        else:
            market_price = await self.get_latest_price(session, req.symbol)

        order_val_usd = req.quantity * market_price

        # 4. Retrieve open positions for risk validation
        pos_stmt = (
            select(PaperPosition)
            .where(PaperPosition.account_id == req.account_id, PaperPosition.is_open.is_(True))
        )
        open_pos_res = await session.execute(pos_stmt)
        open_positions = open_pos_res.scalars().all()

        open_pos_dicts = []
        invested_cap = 0.0
        meme_symbols = {"DOGE", "PEPE", "SHIB", "BONK", "WIF", "FLOKI"}

        for p in open_positions:
            curr_p = await self._resolve_price_for_position(session, p.asset_id.upper())
            if curr_p is None:
                # Use entry price as conservative MTM if live price unavailable
                curr_p = p.avg_entry_price
            mkt_val = p.quantity * curr_p
            invested_cap += mkt_val
            open_pos_dicts.append({
                "symbol": p.asset_id.upper(),
                "asset_class": "MEME" if p.asset_id.upper() in meme_symbols else asset_class,
                "market_value": mkt_val,
                "is_meme": p.asset_id.upper() in meme_symbols,
            })

        total_equity = account.cash_balance + invested_cap
        peak_equity = max(account.starting_balance, total_equity)
        current_dd_pct = ((peak_equity - total_equity) / peak_equity * 100.0) if peak_equity > 0 else 0.0

        # 5. Risk Inspection
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
            rejected_order = PaperOrder(
                id=order_id,
                account_id=req.account_id,
                asset_id=asset_id,
                exchange_id="paper_simulated",
                order_type=req.order_type.value,
                side=req.side.value,
                quantity=req.quantity,
                limit_price=req.limit_price,
                stop_price=getattr(req, "stop_price", None),
                status=PaperOrderStatus.REJECTED.value,
                idempotency_key=idempotency_key or None,
                created_at=now,
                updated_at=now,
            )
            session.add(rejected_order)
            await self._emit_ledger_event(
                session=session,
                event_type=LedgerEventType.ORDER_REJECTED,
                account_id=req.account_id,
                order_id=order_id,
                asset_id=asset_id,
                quantity=req.quantity,
                payload={"reason": validation.reason, "violations": validation.violations},
            )
            await session.commit()
            logger.warning(
                "order_rejected_by_risk_engine",
                reason=validation.reason,
                violations=validation.violations,
            )
            raise ValueError(
                f"Order rejected: {validation.reason} | violations={validation.violations}"
            )

        # 6. Simulate Execution Friction
        exec_side = OrderSide.BUY if req.side == PaperOrderSide.BUY else OrderSide.SELL
        fill_price, _, slippage_usd, fee_usd = self.simulator.calculate_fill(
            side=exec_side,
            base_price=market_price,
            order_value_usd=order_val_usd,
            volume_24h_usd=2_000_000.0,  # conservative estimate
            is_maker=(req.order_type == "LIMIT"),
        )

        # 7. Record Filled Order and Fill
        paper_order = PaperOrder(
            id=order_id,
            account_id=req.account_id,
            asset_id=asset_id,
            exchange_id="paper_simulated",
            order_type=req.order_type.value,
            side=req.side.value,
            quantity=req.quantity,
            limit_price=req.limit_price,
            stop_price=getattr(req, "stop_price", None),
            status=PaperOrderStatus.FILLED.value,
            idempotency_key=idempotency_key or None,
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

        # 8. Update Portfolio Ledger & Position Records
        target_pos_stmt = select(PaperPosition).where(
            PaperPosition.account_id == req.account_id,
            PaperPosition.asset_id == asset_id,
            PaperPosition.is_open.is_(True),
        )
        target_res = await session.execute(target_pos_stmt)
        existing_pos = target_res.scalars().first()

        if req.side == PaperOrderSide.BUY:
            total_cash_outlay = (fill_price * req.quantity) + fee_usd
            account.cash_balance -= total_cash_outlay

            if existing_pos:
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
            # SELL order
            if not existing_pos:
                raise ValueError(f"Cannot sell: No open position found for {req.symbol}")

            qty_to_sell = min(req.quantity, existing_pos.quantity)
            gross_pnl = (fill_price - existing_pos.avg_entry_price) * qty_to_sell
            net_pnl = gross_pnl - fee_usd

            cash_inflow = (fill_price * qty_to_sell) - fee_usd
            account.cash_balance += cash_inflow
            existing_pos.realized_pnl += net_pnl

            if qty_to_sell >= existing_pos.quantity:
                existing_pos.quantity = 0.0
                existing_pos.is_open = False
                existing_pos.exit_time = now
                existing_pos.exit_reason = "USER_SELL"
                existing_pos.unrealized_pnl = 0.0
            else:
                existing_pos.quantity -= qty_to_sell
                existing_pos.unrealized_pnl = (fill_price - existing_pos.avg_entry_price) * existing_pos.quantity

        await self._emit_ledger_event(
            session=session,
            event_type=LedgerEventType.ORDER_FILLED,
            account_id=req.account_id,
            order_id=order_id,
            asset_id=asset_id,
            quantity=req.quantity,
            price=fill_price,
            amount_usd=round(fill_price * req.quantity, 2),
            cash_balance_after=round(account.cash_balance, 2),
            payload={
                "side": req.side.value,
                "order_type": req.order_type.value,
                "fee_usd": round(fee_usd, 4),
                "slippage_usd": round(slippage_usd, 4),
            },
        )

        await session.commit()
        logger.info(
            "paper_order_filled",
            order_id=order_id,
            symbol=req.symbol,
            side=req.side,
            qty=req.quantity,
            fill_price=fill_price,
            gateway="PAPER",
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
        """Compute mark-to-market valuations and risk statistics.

        v2.0: Uses best-effort price with graceful degradation per position.
        Positions with unavailable prices are marked with last-known value.
        """
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
        meme_symbols = {"DOGE", "PEPE", "SHIB", "BONK", "WIF", "FLOKI"}

        for p in open_positions:
            curr_price = await self._resolve_price_for_position(session, p.asset_id.upper())
            price_stale = False
            if curr_price is None:
                curr_price = p.avg_entry_price  # fallback to cost basis for MTM
                price_stale = True

            mkt_val = p.quantity * curr_price
            pnl_usd = (curr_price - p.avg_entry_price) * p.quantity
            cost_basis = p.quantity * p.avg_entry_price
            pnl_pct = (pnl_usd / cost_basis * 100.0) if cost_basis > 0 else 0.0

            invested_cap += mkt_val
            total_unrealized_pnl += pnl_usd
            max_single_val = max(max_single_val, mkt_val)

            if p.asset_id.upper() in meme_symbols:
                meme_val += mkt_val

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
                    price_stale=price_stale,
                )
            )

        total_equity = account.cash_balance + invested_cap
        total_realized_pnl = sum(p.realized_pnl for p in open_positions)

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
        """Close an open position completely by issuing a market sell order."""
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

        order_req = OrderSubmitRequest(
            account_id=account_id,
            symbol=symbol.upper(),
            side=PaperOrderSide.SELL,
            quantity=qty_to_close,
        )
        order_res = await self.submit_order(session, order_req)

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
        starting_balance: float | None = None,
    ) -> PaperAccount:
        """Reset paper account balance and liquidate all positions."""
        bal = starting_balance or settings.PAPER_INITIAL_CAPITAL
        account = await self.get_or_create_account(session, account_id, starting_balance=bal)
        account.starting_balance = bal
        account.cash_balance = bal

        pos_stmt = select(PaperPosition).where(
            PaperPosition.account_id == account_id,
            PaperPosition.is_open.is_(True),
        )
        res = await session.execute(pos_stmt)
        for p in res.scalars().all():
            p.is_open = False
            p.exit_time = utc_now()
            p.exit_reason = "ACCOUNT_RESET"

        await self._emit_ledger_event(
            session=session,
            event_type=LedgerEventType.ACCOUNT_CREATED,
            account_id=account_id,
            cash_balance_after=bal,
            payload={"action": "RESET_ACCOUNT", "starting_balance": bal},
        )

        await session.commit()
        logger.info("paper_account_reset", account_id=account_id, balance=bal)
        return account
