"""Virtual paper brokerage — v2.0 / v3.0.

Key v3.0 changes:
- Exact symbol matching joining Market and OHLCV (eliminates BTC matching WBTC bug)
- Numeric(28, 10) and Decimal precision across all cash, equity, fill, and position accounting
- RiskEngine limits wired directly from Settings
- Resting limit order support via evaluate_resting_orders()
- Idempotency key duplicate detection with DuplicateOrderError
- Append-only immutable ledger events
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backtesting.execution import ExecutionSimulator
from src.backtesting.models import OrderSide, SlippageModelType
from src.config.constants import LedgerEventType
from src.config.exceptions import (
    DuplicateOrderError,
    LiveTradingDisabledError,
    PriceUnavailableError,
    StaleDataError,
)
from src.config.settings import Settings, get_settings
from src.database.models import (
    OHLCV,
    Asset,
    LedgerEvent,
    Market,
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
    PaperOrderType,
    PortfolioSummaryResponse,
    PositionResponse,
)
from src.paper.risk import RiskEngine
from src.utils.logging import get_logger
from src.utils.time import utc_now

logger = get_logger("paper_broker")


def _to_decimal(val: float | int | str | Decimal | None, default: Decimal = Decimal("0.0")) -> Decimal:
    """Safely convert any numeric value or None into a Decimal."""
    if val is None:
        return default
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


class LiveExecutionGateway:
    """v2.0 / v3.0 stub: architecturally disabled live order gateway."""

    def submit(self, *args: Any, **kwargs: Any) -> None:
        raise LiveTradingDisabledError()


class PaperExecutionGateway:
    """Isolated demo execution path. Only PaperBroker instances use this."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def validate_isolation(self) -> None:
        """Assert that live trading is disabled at settings level."""
        if self.settings.LIVE_TRADING_ENABLED:
            raise RuntimeError(
                "CRITICAL: LIVE_TRADING_ENABLED=True detected in settings. "
                "This should be architecturally impossible. "
                "See settings.enforce_live_trading_disabled validator."
            )


class PaperBroker:
    """Virtual broker executing simulated orders with micro-structure friction and portfolio accounting.

    Guarantees:
    1. Never returns a synthetic/fabricated price — raises PriceUnavailableError instead.
    2. Checks idempotency_key to prevent double-order submission.
    3. Exact symbol resolution: BTC never resolves to WBTC or TBTC.
    4. Decimal precision for all monetary columns and balance arithmetic.
    5. Evaluates resting limit orders against candle extremes.
    """

    def __init__(
        self,
        risk_engine: RiskEngine | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.risk_engine = risk_engine or RiskEngine.from_settings(self.settings)
        self.gateway = PaperExecutionGateway(settings=self.settings)
        self.simulator = ExecutionSimulator(
            maker_fee_bps=self.settings.MAKER_FEE_BPS,
            taker_fee_bps=self.settings.TAKER_FEE_BPS,
            slippage_model=SlippageModelType.MARKET_IMPACT,
            impact_gamma=0.1,
        )

    async def get_or_create_account(
        self,
        session: AsyncSession,
        account_id: str = "default_paper",
        name: str = "Primary Paper Portfolio",
        starting_balance: float | Decimal | None = None,
    ) -> PaperAccount:
        """Fetch existing paper account or initialize a new virtual ledger."""
        stmt = select(PaperAccount).where(PaperAccount.id == account_id)
        res = await session.execute(stmt)
        account = res.scalars().first()

        if not account:
            raw_bal = starting_balance if starting_balance is not None else self.settings.PAPER_INITIAL_CAPITAL
            bal = _to_decimal(raw_bal)
            account = PaperAccount(
                id=account_id,
                name=name,
                base_currency="USD",
                starting_balance=bal,
                cash_balance=bal,
                created_at=utc_now(),
            )
            session.add(account)
            await self._emit_ledger_event(
                session=session,
                event_type=LedgerEventType.ACCOUNT_CREATED,
                account_id=account_id,
                cash_balance_after=bal,
                amount_usd=bal,
                payload={"action": "INIT_ACCOUNT", "starting_balance": float(bal)},
            )
            await session.commit()
            logger.info(
                "Initialized new paper trading account",
                account_id=account_id,
                balance=float(bal),
            )

        return account

    async def get_latest_price(
        self,
        session: AsyncSession,
        symbol: str,
        *,
        quote_asset: str = "USDT",
        max_age_seconds: int | None = None,
    ) -> Decimal:
        """Fetch latest validated market price for an asset symbol from the DB.

        Exact symbol matching:
        1. Joins Market and OHLCV on market_id == Market.id where asset_id == symbol.
        2. Fallback to exact market_id pattern matching on OHLCV.market_id.

        Raises:
            PriceUnavailableError: no candle found in DB for this symbol
            StaleDataError: candle found but older than threshold
        """
        threshold = max_age_seconds or self.settings.PRICE_STALE_THRESHOLD_SECONDS
        sym_clean = symbol.upper()
        quote_clean = quote_asset.upper()

        # 1. Exact match via Market join
        stmt_market = (
            select(OHLCV)
            .join(Market, OHLCV.market_id == Market.id)
            .where(
                Market.asset_id == sym_clean,
                Market.quote_asset == quote_clean,
            )
            .order_by(desc(OHLCV.time))
            .limit(1)
        )
        res = await session.execute(stmt_market)
        candle = res.scalars().first()

        # 2. Fallback exact pattern matching if Market table wasn't seeded
        if candle is None:
            stmt_pattern = (
                select(OHLCV)
                .where(
                    (OHLCV.market_id == f"{sym_clean}/{quote_clean}")
                    | (OHLCV.market_id.like(f"%:{sym_clean}/{quote_clean}"))
                    | (OHLCV.market_id.like(f"%:{sym_clean}/{quote_clean}:%"))
                    | (OHLCV.market_id == sym_clean)
                )
                .order_by(desc(OHLCV.time))
                .limit(1)
            )
            res = await session.execute(stmt_pattern)
            candle = res.scalars().first()

        if candle is None:
            raise PriceUnavailableError(
                symbol=symbol,
                source="ohlcv_db",
                details=f"No OHLCV record found for {symbol}/{quote_asset}. Run market data ingestion first.",
            )

        if candle.close is None or candle.close <= 0:
            raise PriceUnavailableError(
                symbol=symbol,
                source="ohlcv_db",
                details=f"Most recent OHLCV record for {symbol} has null or zero close price.",
            )

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

        return Decimal(str(candle.close))

    async def _resolve_price_for_position(
        self,
        session: AsyncSession,
        symbol: str,
        quote_asset: str = "USDT",
    ) -> Decimal | None:
        """Resolve best-effort price for mark-to-market of existing positions."""
        try:
            return await self.get_latest_price(
                session, symbol, quote_asset=quote_asset, max_age_seconds=self.settings.PRICE_STALE_THRESHOLD_SECONDS * 3
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
        quantity: Decimal | float | None = None,
        price: Decimal | float | None = None,
        amount_usd: Decimal | float | None = None,
        cash_balance_after: Decimal | float | None = None,
        payload: dict | None = None,
    ) -> LedgerEvent:
        """Record an immutable ledger event for audit and state recovery — v2.0 / v3.0."""
        import json

        ev = LedgerEvent(
            id=str(uuid.uuid4()),
            event_type=str(event_type.value if hasattr(event_type, "value") else event_type),
            account_id=account_id,
            order_id=order_id,
            asset_id=asset_id,
            quantity=_to_decimal(quantity) if quantity is not None else None,
            price=_to_decimal(price) if price is not None else None,
            amount_usd=_to_decimal(amount_usd) if amount_usd is not None else None,
            cash_balance_after=_to_decimal(cash_balance_after) if cash_balance_after is not None else None,
            payload_json=json.dumps(payload) if payload else None,
            data_mode=self.settings.DATA_MODE.value,
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
        # 0. Isolation guard
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
        asset_id = asset.id if asset else req.symbol.upper()
        asset_class = str(asset.asset_class.value) if asset and hasattr(asset.asset_class, "value") else "ALTCOIN"

        # 3. Get current market price
        market_price = await self.get_latest_price(session, req.symbol)
        qty_dec = _to_decimal(req.quantity)
        order_val_usd = qty_dec * market_price

        # 4. Retrieve open positions for risk validation
        pos_stmt = (
            select(PaperPosition)
            .where(PaperPosition.account_id == req.account_id, PaperPosition.is_open.is_(True))
        )
        open_pos_res = await session.execute(pos_stmt)
        open_positions = open_pos_res.scalars().all()

        open_pos_dicts = []
        invested_cap = Decimal("0.0")
        meme_symbols = {"DOGE", "PEPE", "SHIB", "BONK", "WIF", "FLOKI"}

        for p in open_positions:
            curr_p = await self._resolve_price_for_position(session, p.asset_id.upper())
            if curr_p is None:
                curr_p = _to_decimal(p.avg_entry_price)
            mkt_val = _to_decimal(p.quantity) * curr_p
            invested_cap += mkt_val
            open_pos_dicts.append({
                "symbol": p.asset_id.upper(),
                "asset_class": "MEME" if p.asset_id.upper() in meme_symbols else asset_class,
                "market_value": float(mkt_val),
                "is_meme": p.asset_id.upper() in meme_symbols,
            })

        total_equity = _to_decimal(account.cash_balance) + invested_cap
        starting_bal = _to_decimal(account.starting_balance)
        peak_equity = max(starting_bal, total_equity)
        current_dd_pct = ((peak_equity - total_equity) / peak_equity * Decimal("100.0")) if peak_equity > 0 else Decimal("0.0")

        # 5. Risk Inspection
        validation = self.risk_engine.validate_order(
            side=req.side,
            asset_symbol=req.symbol.upper(),
            asset_class=asset_class,
            order_value_usd=order_val_usd,
            cash_balance=_to_decimal(account.cash_balance),
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
                quantity=qty_dec,
                limit_price=_to_decimal(req.limit_price) if req.limit_price else None,
                stop_price=_to_decimal(getattr(req, "stop_price", None)) if getattr(req, "stop_price", None) else None,
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
                quantity=qty_dec,
                price=market_price,
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

        # 6. Check for resting limit order
        is_limit = req.order_type in {PaperOrderType.LIMIT, "LIMIT"} and req.limit_price is not None
        is_resting = False
        if is_limit:
            lim_dec = _to_decimal(req.limit_price)
            if req.side == PaperOrderSide.BUY and lim_dec < market_price:
                is_resting = True
            elif req.side == PaperOrderSide.SELL and lim_dec > market_price:
                is_resting = True

        if is_resting:
            resting_order = PaperOrder(
                id=order_id,
                account_id=req.account_id,
                asset_id=asset_id,
                exchange_id="paper_simulated",
                order_type=req.order_type.value,
                side=req.side.value,
                quantity=qty_dec,
                limit_price=_to_decimal(req.limit_price),
                stop_price=_to_decimal(getattr(req, "stop_price", None)) if getattr(req, "stop_price", None) else None,
                status=PaperOrderStatus.OPEN.value,
                idempotency_key=idempotency_key or None,
                created_at=now,
                updated_at=now,
            )
            session.add(resting_order)
            await self._emit_ledger_event(
                session=session,
                event_type="ORDER_RESTING",
                account_id=req.account_id,
                order_id=order_id,
                asset_id=asset_id,
                quantity=qty_dec,
                price=_to_decimal(req.limit_price),
                payload={"reason": "Resting limit order placed below/above market"},
            )
            await session.commit()
            logger.info("paper_order_resting", order_id=order_id, symbol=req.symbol, limit_price=req.limit_price)

            return OrderResponse(
                id=order_id,
                account_id=req.account_id,
                symbol=req.symbol.upper(),
                side=req.side.value,
                order_type=req.order_type.value,
                quantity=float(qty_dec),
                status=PaperOrderStatus.OPEN.value,
                fills=[],
                created_at=now.isoformat(),
            )

        # 7. Simulate Execution Friction for Immediate Fill
        exec_side = OrderSide.BUY if req.side == PaperOrderSide.BUY else OrderSide.SELL
        fill_price_flt, _, slippage_flt, fee_flt = self.simulator.calculate_fill(
            side=exec_side,
            base_price=float(market_price),
            order_value_usd=float(order_val_usd),
            volume_24h_usd=2_000_000.0,
            is_maker=is_limit,
        )

        fill_price = round(_to_decimal(fill_price_flt), 4)
        fee_usd = round(_to_decimal(fee_flt), 4)
        slippage_usd = round(_to_decimal(slippage_flt), 4)

        paper_order = PaperOrder(
            id=order_id,
            account_id=req.account_id,
            asset_id=asset_id,
            exchange_id="paper_simulated",
            order_type=req.order_type.value,
            side=req.side.value,
            quantity=qty_dec,
            limit_price=_to_decimal(req.limit_price) if req.limit_price else None,
            stop_price=_to_decimal(getattr(req, "stop_price", None)) if getattr(req, "stop_price", None) else None,
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
            fill_price=fill_price,
            quantity=qty_dec,
            fee_usd=fee_usd,
            slippage_usd=slippage_usd,
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
            total_cash_outlay = (fill_price * qty_dec) + fee_usd
            account.cash_balance = _to_decimal(account.cash_balance) - total_cash_outlay

            if existing_pos:
                prev_qty = _to_decimal(existing_pos.quantity)
                prev_entry = _to_decimal(existing_pos.avg_entry_price)
                new_qty = prev_qty + qty_dec
                new_avg_entry = ((prev_qty * prev_entry) + (qty_dec * fill_price)) / new_qty
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
                    quantity=qty_dec,
                    avg_entry_price=fill_price,
                    current_price=fill_price,
                    unrealized_pnl=Decimal("0.0"),
                    realized_pnl=Decimal("0.0"),
                    entry_time=now,
                    is_open=True,
                )
                session.add(new_pos)

        else:
            # SELL order
            if not existing_pos:
                raise ValueError(f"Cannot sell: No open position found for {req.symbol}")

            prev_qty = _to_decimal(existing_pos.quantity)
            prev_entry = _to_decimal(existing_pos.avg_entry_price)
            qty_to_sell = min(qty_dec, prev_qty)
            gross_pnl = (fill_price - prev_entry) * qty_to_sell
            net_pnl = gross_pnl - fee_usd

            cash_inflow = (fill_price * qty_to_sell) - fee_usd
            account.cash_balance = _to_decimal(account.cash_balance) + cash_inflow
            existing_pos.realized_pnl = _to_decimal(existing_pos.realized_pnl) + net_pnl

            if qty_to_sell >= prev_qty:
                existing_pos.quantity = Decimal("0.0")
                existing_pos.is_open = False
                existing_pos.exit_time = now
                existing_pos.exit_reason = "USER_SELL"
                existing_pos.unrealized_pnl = Decimal("0.0")
            else:
                rem_qty = prev_qty - qty_to_sell
                existing_pos.quantity = rem_qty
                existing_pos.unrealized_pnl = (fill_price - prev_entry) * rem_qty

        await self._emit_ledger_event(
            session=session,
            event_type=LedgerEventType.ORDER_FILLED,
            account_id=req.account_id,
            order_id=order_id,
            asset_id=asset_id,
            quantity=qty_dec,
            price=fill_price,
            amount_usd=round(fill_price * qty_dec, 2),
            cash_balance_after=round(account.cash_balance, 2),
            payload={
                "side": req.side.value,
                "order_type": req.order_type.value,
                "fee_usd": float(fee_usd),
                "slippage_usd": float(slippage_usd),
            },
        )

        await session.commit()
        logger.info(
            "paper_order_filled",
            order_id=order_id,
            symbol=req.symbol,
            side=req.side,
            qty=float(qty_dec),
            fill_price=float(fill_price),
            gateway="PAPER",
        )

        return OrderResponse(
            id=order_id,
            account_id=req.account_id,
            symbol=req.symbol.upper(),
            side=req.side.value,
            order_type=req.order_type.value,
            quantity=float(qty_dec),
            status=PaperOrderStatus.FILLED.value,
            fills=[
                FillResponse(
                    id=fill_id,
                    order_id=order_id,
                    time=now.isoformat(),
                    fill_price=float(fill_price),
                    quantity=float(qty_dec),
                    fee_usd=float(fee_usd),
                    slippage_usd=float(slippage_usd),
                )
            ],
            created_at=now.isoformat(),
        )

    async def evaluate_resting_orders(
        self,
        session: AsyncSession,
        candle: OHLCV,
    ) -> list[PaperOrder]:
        """Evaluate resting limit orders against a newly arrived candle bar.

        Executes resting orders if their limit price is crossed by the candle high/low range.
        """
        # Find all open resting orders
        stmt = select(PaperOrder).where(
            PaperOrder.status.in_([PaperOrderStatus.OPEN.value, PaperOrderStatus.PENDING.value])
        )
        res = await session.execute(stmt)
        resting_orders = res.scalars().all()

        filled_orders: list[PaperOrder] = []
        if not resting_orders:
            return filled_orders

        # Determine candle asset ID
        candle_mkt = candle.market_id or ""
        # e.g. "binance:BTC/USDT" -> "BTC", "BTC/USDT" -> "BTC"
        clean_mkt = candle_mkt.split(":")[-1] if ":" in candle_mkt else candle_mkt
        candle_asset = clean_mkt.split("/")[0].upper() if "/" in clean_mkt else clean_mkt.upper()

        c_open = _to_decimal(candle.open)
        c_high = _to_decimal(candle.high)
        c_low = _to_decimal(candle.low)

        now = utc_now()

        for order in resting_orders:
            if order.asset_id.upper() != candle_asset or order.limit_price is None:
                continue

            lim_p = _to_decimal(order.limit_price)
            should_fill = False
            exec_price = lim_p

            if order.side == PaperOrderSide.BUY.value and c_low <= lim_p:
                should_fill = True
                exec_price = min(lim_p, c_open)
            elif order.side == PaperOrderSide.SELL.value and c_high >= lim_p:
                should_fill = True
                exec_price = max(lim_p, c_open)

            if should_fill:
                # Calculate maker fee
                fee_flt = float(exec_price * order.quantity) * (self.settings.MAKER_FEE_BPS / 10000.0)
                fee_usd = round(_to_decimal(fee_flt), 4)

                order.status = PaperOrderStatus.FILLED.value
                order.updated_at = now

                fill_id = str(uuid.uuid4())
                fill_record = PaperFill(
                    id=fill_id,
                    order_id=order.id,
                    time=now,
                    fill_price=exec_price,
                    quantity=order.quantity,
                    fee_usd=fee_usd,
                    slippage_usd=Decimal("0.0"),
                )
                session.add(fill_record)

                # Update Account and Position
                account_stmt = select(PaperAccount).where(PaperAccount.id == order.account_id)
                account_res = await session.execute(account_stmt)
                account = account_res.scalars().first()

                if account:
                    pos_stmt = select(PaperPosition).where(
                        PaperPosition.account_id == order.account_id,
                        PaperPosition.asset_id == order.asset_id,
                        PaperPosition.is_open.is_(True),
                    )
                    pos_res = await session.execute(pos_stmt)
                    existing_pos = pos_res.scalars().first()

                    if order.side == PaperOrderSide.BUY.value:
                        total_outlay = (exec_price * order.quantity) + fee_usd
                        account.cash_balance = _to_decimal(account.cash_balance) - total_outlay
                        if existing_pos:
                            prev_q = _to_decimal(existing_pos.quantity)
                            prev_e = _to_decimal(existing_pos.avg_entry_price)
                            new_q = prev_q + order.quantity
                            new_e = ((prev_q * prev_e) + (order.quantity * exec_price)) / new_q
                            existing_pos.quantity = new_q
                            existing_pos.avg_entry_price = new_e
                            existing_pos.current_price = exec_price
                            existing_pos.unrealized_pnl = (exec_price - new_e) * new_q
                        else:
                            new_pos = PaperPosition(
                                id=str(uuid.uuid4()),
                                account_id=order.account_id,
                                asset_id=order.asset_id,
                                side="LONG",
                                quantity=order.quantity,
                                avg_entry_price=exec_price,
                                current_price=exec_price,
                                unrealized_pnl=Decimal("0.0"),
                                realized_pnl=Decimal("0.0"),
                                entry_time=now,
                                is_open=True,
                            )
                            session.add(new_pos)
                    else:
                        if existing_pos:
                            prev_q = _to_decimal(existing_pos.quantity)
                            prev_e = _to_decimal(existing_pos.avg_entry_price)
                            qty_to_sell = min(order.quantity, prev_q)
                            gross_pnl = (exec_price - prev_e) * qty_to_sell
                            net_pnl = gross_pnl - fee_usd
                            account.cash_balance = _to_decimal(account.cash_balance) + ((exec_price * qty_to_sell) - fee_usd)
                            existing_pos.realized_pnl = _to_decimal(existing_pos.realized_pnl) + net_pnl
                            if qty_to_sell >= prev_q:
                                existing_pos.quantity = Decimal("0.0")
                                existing_pos.is_open = False
                                existing_pos.exit_time = now
                                existing_pos.exit_reason = "LIMIT_SELL"
                                existing_pos.unrealized_pnl = Decimal("0.0")
                            else:
                                rem_q = prev_q - qty_to_sell
                                existing_pos.quantity = rem_q
                                existing_pos.unrealized_pnl = (exec_price - prev_e) * rem_q

                    await self._emit_ledger_event(
                        session=session,
                        event_type=LedgerEventType.ORDER_FILLED,
                        account_id=order.account_id,
                        order_id=order.id,
                        asset_id=order.asset_id,
                        quantity=order.quantity,
                        price=exec_price,
                        amount_usd=round(exec_price * order.quantity, 2),
                        cash_balance_after=round(account.cash_balance, 2),
                        payload={
                            "side": order.side,
                            "order_type": "LIMIT",
                            "fee_usd": float(fee_usd),
                            "slippage_usd": 0.0,
                        },
                    )

                filled_orders.append(order)

        if filled_orders:
            await session.commit()
            logger.info("resting_orders_executed", count=len(filled_orders))

        return filled_orders

    async def get_portfolio_summary(
        self,
        session: AsyncSession,
        account_id: str = "default_paper",
    ) -> PortfolioSummaryResponse:
        """Compute mark-to-market valuations and risk statistics."""
        account = await self.get_or_create_account(session, account_id)

        pos_stmt = (
            select(PaperPosition)
            .where(PaperPosition.account_id == account_id, PaperPosition.is_open.is_(True))
        )
        pos_res = await session.execute(pos_stmt)
        open_positions = pos_res.scalars().all()

        position_responses: list[PositionResponse] = []
        invested_cap = Decimal("0.0")
        total_unrealized_pnl = Decimal("0.0")
        meme_val = Decimal("0.0")
        max_single_val = Decimal("0.0")
        meme_symbols = {"DOGE", "PEPE", "SHIB", "BONK", "WIF", "FLOKI"}

        for p in open_positions:
            curr_price = await self._resolve_price_for_position(session, p.asset_id.upper())
            price_stale = False
            if curr_price is None:
                curr_price = _to_decimal(p.avg_entry_price)
                price_stale = True

            p_qty = _to_decimal(p.quantity)
            p_entry = _to_decimal(p.avg_entry_price)
            mkt_val = p_qty * curr_price
            pnl_usd = (curr_price - p_entry) * p_qty
            cost_basis = p_qty * p_entry
            pnl_pct = ((pnl_usd / cost_basis) * Decimal("100.0")) if cost_basis > 0 else Decimal("0.0")

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
                    quantity=float(p_qty),
                    avg_entry_price=float(round(p_entry, 4)),
                    current_price=float(round(curr_price, 4)),
                    market_value=float(round(mkt_val, 2)),
                    unrealized_pnl=float(round(pnl_usd, 2)),
                    unrealized_pnl_pct=float(round(pnl_pct, 2)),
                    realized_pnl=float(round(_to_decimal(p.realized_pnl), 2)),
                    entry_time=p.entry_time.isoformat(),
                    exit_time=p.exit_time.isoformat() if p.exit_time else None,
                    is_open=p.is_open,
                    exit_reason=p.exit_reason,
                    price_stale=price_stale,
                )
            )

        acct_cash = _to_decimal(account.cash_balance)
        acct_start = _to_decimal(account.starting_balance)
        total_equity = acct_cash + invested_cap
        total_realized_pnl = sum((_to_decimal(p.realized_pnl) for p in open_positions), Decimal("0.0"))

        closed_stmt = select(PaperPosition.realized_pnl).where(
            PaperPosition.account_id == account_id, PaperPosition.is_open.is_(False)
        )
        closed_res = await session.execute(closed_stmt)
        total_realized_pnl += sum((_to_decimal(r) for r in closed_res.scalars().all()), Decimal("0.0"))

        total_pnl = total_unrealized_pnl + total_realized_pnl
        total_return_pct = (((total_equity - acct_start) / acct_start) * Decimal("100.0")) if acct_start > 0 else Decimal("0.0")

        peak_equity = max(acct_start, total_equity)
        drawdown_pct = (((peak_equity - total_equity) / peak_equity) * Decimal("100.0")) if peak_equity > 0 else Decimal("0.0")

        meme_exposure_pct = ((meme_val / total_equity) * Decimal("100.0")) if total_equity > 0 else Decimal("0.0")
        max_single_position_pct = ((max_single_val / total_equity) * Decimal("100.0")) if total_equity > 0 else Decimal("0.0")

        now = utc_now()
        session.add(
            PaperEquity(
                time=now,
                account_id=account_id,
                equity=round(total_equity, 4),
                cash=round(acct_cash, 4),
                invested_capital=round(invested_cap, 4),
                unrealized_pnl=round(total_unrealized_pnl, 4),
                realized_pnl=round(total_realized_pnl, 4),
                drawdown_pct=round(drawdown_pct, 4),
            )
        )
        session.add(
            PortfolioSnapshot(
                time=now,
                account_id=account_id,
                gross_exposure=round(invested_cap, 4),
                net_exposure=round(invested_cap, 4),
                meme_exposure_pct=round(meme_exposure_pct, 4),
                max_single_position_pct=round(max_single_position_pct, 4),
                positions_count=len(open_positions),
            )
        )
        await session.commit()

        return PortfolioSummaryResponse(
            account_id=account.id,
            name=account.name,
            base_currency=account.base_currency,
            starting_balance=float(round(acct_start, 2)),
            cash_balance=float(round(acct_cash, 2)),
            invested_capital=float(round(invested_cap, 2)),
            total_equity=float(round(total_equity, 2)),
            unrealized_pnl=float(round(total_unrealized_pnl, 2)),
            realized_pnl=float(round(total_realized_pnl, 2)),
            total_pnl=float(round(total_pnl, 2)),
            total_return_pct=float(round(total_return_pct, 2)),
            drawdown_pct=float(round(drawdown_pct, 2)),
            peak_equity=float(round(peak_equity, 2)),
            gross_exposure=float(round(invested_cap, 2)),
            net_exposure=float(round(invested_cap, 2)),
            meme_exposure_pct=float(round(meme_exposure_pct, 2)),
            max_single_position_pct=float(round(max_single_position_pct, 2)),
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

        if not pos or _to_decimal(pos.quantity) <= 0:
            raise ValueError(f"No active open position found for {symbol}")

        qty_to_close = float(pos.quantity)
        avg_entry = float(pos.avg_entry_price)

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

        curr_p = order_res.fills[0].fill_price if order_res.fills else float(pos.current_price)
        cost_basis = avg_entry * qty_to_close
        realized_pnl_flt = float(pos.realized_pnl)
        pnl_pct = (realized_pnl_flt / cost_basis * 100.0) if cost_basis > 0 else 0.0

        return PositionResponse(
            id=pos.id,
            account_id=pos.account_id,
            symbol=pos.asset_id.upper(),
            side=pos.side,
            quantity=0.0,
            avg_entry_price=round(avg_entry, 4),
            current_price=round(curr_p, 4),
            market_value=0.0,
            unrealized_pnl=0.0,
            unrealized_pnl_pct=round(pnl_pct, 2),
            realized_pnl=round(realized_pnl_flt, 2),
            entry_time=pos.entry_time.isoformat(),
            exit_time=pos.exit_time.isoformat() if pos.exit_time else utc_now().isoformat(),
            is_open=False,
            exit_reason=pos.exit_reason,
        )

    async def reset_account(
        self,
        session: AsyncSession,
        account_id: str = "default_paper",
        starting_balance: float | Decimal | None = None,
    ) -> PaperAccount:
        """Reset paper account balance and liquidate all positions."""
        raw_bal = starting_balance if starting_balance is not None else self.settings.PAPER_INITIAL_CAPITAL
        bal = _to_decimal(raw_bal)
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
            amount_usd=bal,
            payload={"action": "RESET_ACCOUNT", "starting_balance": float(bal)},
        )

        await session.commit()
        logger.info("paper_account_reset", account_id=account_id, balance=float(bal))
        return account
