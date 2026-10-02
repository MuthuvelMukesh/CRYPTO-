# Runbook: Paper Trading Ledger Discrepancy & Reconciliation

**Severity**: P1 (Accounting Integrity Violation)  
**Applies to**: Paper Brokerage, `ledger_events`, `paper_accounts`, `reconcile_account_ledger`

---

## 1. Overview
Platform v3.0 enforces double-entry, append-only accounting on all virtual paper trading transactions.
- Every cash deposit, trade execution, and fee deduction writes an immutable `LedgerEvent`.
- The database enforces triggers and ORM listeners prohibiting `UPDATE` or `DELETE` on `ledger_events`.
- An authoritative reconciliation job replays all events from time zero to verify:
$$\text{Account Cash Balance} \equiv \sum \text{Ledger Cash Deltas}$$

---

## 2. Detection & Alerts
- Prometheus metric: `crypto_ledger_reconciliation_status == 0.0` (discrepancy detected).
- API endpoint `GET /api/v1/paper/reconcile` returns:
  ```json
  {
    "is_balanced": false,
    "account_id": "default_paper",
    "stored_cash": 95000.0,
    "calculated_cash": 94850.0,
    "discrepancy": 150.0
  }
  ```
- Error log: `ledger_reconciliation_failed_discrepancy_detected`.

---

## 3. Investigation & Recovery Protocol

### Step 1: Execute Authoritative Reconciliation Drill
Run the reconciliation script from the repository root:
```bash
python -m src.paper.reconcile --account-id default_paper
```
Or via HTTP API:
```bash
curl -s -H "X-API-Key: dev-api-key-researcher-1" "http://localhost:8000/api/v1/paper/reconcile?account_id=default_paper" | jq .
```

### Step 2: Query Missing or Unbalanced Ledger Events
Inspect the most recent orders and ledger events:
```sql
SELECT id, event_type, order_id, asset_id, quantity, price, amount_usd, cash_balance_after, created_at
FROM ledger_events
WHERE account_id = 'default_paper'
ORDER BY created_at DESC
LIMIT 20;
```
Check if an order fill occurred without an accompanying ledger event (e.g. unhandled database crash mid-transaction).

### Step 3: Audit Idempotency Violations
Verify if duplicate client requests bypassed concurrency guards:
```sql
SELECT idempotency_key, count(*)
FROM paper_orders
GROUP BY idempotency_key
HAVING count(*) > 1;
```
(Should always be 0 due to unique index).

### Step 4: Corrective Action
Because `ledger_events` is immutable, never manually mutate existing rows.
If an unexplained ledger delta exists:
1. Re-align the account state by writing an explicit compensating `ADJUSTMENT` event to the ledger:
   ```python
   # Example: write balancing ledger event
   adjustment_event = LedgerEvent(
       event_type="AUDIT_ADJUSTMENT",
       account_id="default_paper",
       amount_usd=discrepancy_amount,
       payload_json=json.dumps({"reason": "Manual audit alignment per runbook"}),
   )
   ```
2. Re-run `python -m src.paper.reconcile` to confirm `is_balanced == True`.
