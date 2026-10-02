# Runbook: Exchange Outage & Fallback Failover

**Severity**: P1 (Primary Venue Outage)  
**Applies to**: CCXT Provider Layer, Ingestion Fallback Manager (`ExchangeFallbackManager`)

---

## 1. Overview
Platform v3.0 maintains a multi-exchange failover router:
$$\text{Binance} \longrightarrow \text{Coinbase} \longrightarrow \text{Kraken}$$
When 3 consecutive network failures or an HTTP 429 status code are encountered on the primary exchange, the system automatically redirects ingestion to the next healthy venue in the chain and enforces a 15-minute cooldown before attempting to probe the primary venue.

---

## 2. Detection & Alerts
- Log event: `exchange_fallback_triggered` with `from_exchange` and `to_exchange`.
- Table `exchange_failovers`: records incident timestamp, source, target, and failure reason.
- Prometheus metric: `crypto_ingestion_lag_seconds{exchange="binance"}` increasing while `{exchange="coinbase"}` remains active.

---

## 3. Investigation & Verification Steps

### Step 1: Query Failover Event Records
Query recent failover events via database or API:
```sql
SELECT time, from_exchange, to_exchange, reason
FROM exchange_failovers
ORDER BY time DESC
LIMIT 10;
```

### Step 2: Validate Secondary Feed Quality
Verify that Coinbase / Kraken candles are being mapped correctly to canonical asset symbols (e.g. `coinbase:BTC/USD` or `binance:BTC/USDT`):
```bash
curl -s -H "X-API-Key: dev-api-key-researcher-1" "http://localhost:8000/api/v1/assets/BTC" | jq .markets
```

### Step 3: Manual Venue Override (If Necessary)
If an exchange outage is expected to persist for hours (e.g. planned maintenance), update the fallback order in `.env`:
```env
DEFAULT_EXCHANGE=coinbase
EXCHANGE_FALLBACK_ORDER=coinbase,kraken,binance
```
Restart the worker:
```bash
docker compose up -d --no-deps worker
```

### Step 4: Cooldown Recovery
The `ExchangeFallbackManager` will automatically attempt to resume traffic to Binance once the 15-minute cooldown expires. Monitor worker logs for:
`exchange_fallback_recovered: successfully switched back to binance`
