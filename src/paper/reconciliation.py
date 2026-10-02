"""Authoritative paper trading ledger reconciliation.

Replays immutable ledger events from inception to reconstruct cash balances and
positions, detecting any data corruption, drift, or unauthorized tampering.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import LedgerEvent, PaperAccount, PaperPosition
from src.database.session import get_db_session
from src.utils.logging import get_logger

logger = get_logger("ledger_reconciliation")


class ReconciliationResult(BaseModel):
    """Result of ledger event replay and consistency audit."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    account_id: str
    passed: bool
    discrepancy_count: int
    discrepancies: list[str]
    replayed_cash: Decimal
    actual_cash: Decimal
    replayed_positions: dict[str, Decimal]
    actual_positions: dict[str, Decimal]
    events_replayed: int


async def reconcile_account_ledger(
    session: AsyncSession,
    account_id: str = "default_paper",
) -> ReconciliationResult:
    """Reconstruct account state from ledger events and verify against DB tables."""
    # 1. Fetch current account record
    acct_stmt = select(PaperAccount).where(PaperAccount.id == account_id)
    acct_res = await session.execute(acct_stmt)
    account = acct_res.scalars().first()

    if not account:
        return ReconciliationResult(
            account_id=account_id,
            passed=False,
            discrepancy_count=1,
            discrepancies=[f"Account '{account_id}' does not exist in paper_accounts table."],
            replayed_cash=Decimal("0.0"),
            actual_cash=Decimal("0.0"),
            replayed_positions={},
            actual_positions={},
            events_replayed=0,
        )

    # 2. Fetch all ledger events chronologically
    events_stmt = (
        select(LedgerEvent)
        .where(LedgerEvent.account_id == account_id)
        .order_by(LedgerEvent.created_at.asc(), LedgerEvent.id.asc())
    )
    events_res = await session.execute(events_stmt)
    events = events_res.scalars().all()

    replayed_cash = Decimal("0.0")
    replayed_positions: dict[str, Decimal] = {}
    discrepancies: list[str] = []

    for ev in events:
        payload: dict[str, Any] = {}
        if ev.payload_json:
            try:
                payload = json.loads(ev.payload_json)
            except Exception:
                payload = {}

        ev_type = str(ev.event_type).upper()

        if ev_type in {"ACCOUNT_CREATED", "RESET_ACCOUNT"}:
            if "starting_balance" in payload:
                replayed_cash = Decimal(str(payload["starting_balance"]))
            elif ev.cash_balance_after is not None:
                replayed_cash = Decimal(str(ev.cash_balance_after))
            elif ev.amount_usd is not None:
                replayed_cash = Decimal(str(ev.amount_usd))
            replayed_positions.clear()

        elif ev_type == "ORDER_FILLED":
            side = str(payload.get("side", "BUY")).upper()
            qty = Decimal(str(ev.quantity or 0.0))
            price = Decimal(str(ev.price or 0.0))
            fee = Decimal(str(payload.get("fee_usd", 0.0)))
            asset = (ev.asset_id or "").upper()

            if side == "BUY":
                cash_outlay = (qty * price) + fee
                replayed_cash -= cash_outlay
                if asset:
                    replayed_positions[asset] = replayed_positions.get(asset, Decimal("0.0")) + qty
            elif side == "SELL":
                cash_inflow = (qty * price) - fee
                replayed_cash += cash_inflow
                if asset:
                    curr_qty = replayed_positions.get(asset, Decimal("0.0"))
                    new_qty = curr_qty - qty
                    if new_qty <= Decimal("1e-8"):
                        replayed_positions.pop(asset, None)
                    else:
                        replayed_positions[asset] = new_qty

        elif ev_type in {"DEPOSIT", "FUNDS_ADDED"}:
            amt = Decimal(str(ev.amount_usd or 0.0))
            replayed_cash += amt

        elif ev_type in {"WITHDRAWAL", "FUNDS_REMOVED"}:
            amt = Decimal(str(ev.amount_usd or 0.0))
            replayed_cash -= amt

    # 3. Compare replayed cash against actual DB cash_balance
    actual_cash = Decimal(str(account.cash_balance))
    cash_diff = abs(actual_cash - replayed_cash)
    if cash_diff > Decimal("0.01"):
        discrepancies.append(
            f"Cash mismatch: account cash=${actual_cash:.2f}, replayed cash=${replayed_cash:.2f} (diff=${cash_diff:.2f})"
        )

    # 4. Compare open positions against DB paper_positions
    pos_stmt = select(PaperPosition).where(
        PaperPosition.account_id == account_id,
        PaperPosition.is_open.is_(True),
    )
    pos_res = await session.execute(pos_stmt)
    actual_pos_list = pos_res.scalars().all()
    actual_positions: dict[str, Decimal] = {
        p.asset_id.upper(): Decimal(str(p.quantity))
        for p in actual_pos_list
        if Decimal(str(p.quantity)) > Decimal("1e-8")
    }

    # Verify each DB open position matches replayed quantity
    for asset, db_qty in actual_positions.items():
        rep_qty = replayed_positions.get(asset, Decimal("0.0"))
        qty_diff = abs(db_qty - rep_qty)
        if qty_diff > Decimal("1e-6"):
            discrepancies.append(
                f"Position mismatch for {asset}: DB open quantity={db_qty}, replayed quantity={rep_qty}"
            )

    # Verify no orphan replayed positions missing from DB
    for asset, rep_qty in replayed_positions.items():
        if rep_qty > Decimal("1e-6") and asset not in actual_positions:
            discrepancies.append(
                f"Orphan replayed position: {asset} has replayed quantity={rep_qty} but is closed or missing in DB"
            )

    passed = len(discrepancies) == 0
    if not passed:
        logger.warning(
            "ledger_reconciliation_failed",
            account_id=account_id,
            discrepancies=discrepancies,
        )
    else:
        logger.info(
            "ledger_reconciliation_passed",
            account_id=account_id,
            events_replayed=len(events),
            cash=replayed_cash,
        )

    return ReconciliationResult(
        account_id=account_id,
        passed=passed,
        discrepancy_count=len(discrepancies),
        discrepancies=discrepancies,
        replayed_cash=replayed_cash,
        actual_cash=actual_cash,
        replayed_positions=replayed_positions,
        actual_positions=actual_positions,
        events_replayed=len(events),
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile paper trading ledger events.")
    parser.add_argument("--account-id", default="default_paper", help="Paper account identifier")
    args = parser.parse_args()

    async for session in get_db_session():
        res = await reconcile_account_ledger(session, account_id=args.account_id)
        print(f"Reconciliation for {res.account_id}: {'PASSED' if res.passed else 'FAILED'}")
        print(f"Events replayed: {res.events_replayed}")
        print(f"Replayed Cash: ${res.replayed_cash:,.2f} | Actual Cash: ${res.actual_cash:,.2f}")
        if res.discrepancies:
            print("Discrepancies:")
            for d in res.discrepancies:
                print(f"  - {d}")


if __name__ == "__main__":
    asyncio.run(main())
