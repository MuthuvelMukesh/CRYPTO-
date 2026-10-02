# Runbook: Stale Market Data Detection & Recovery

**Severity**: P2 (Operational Degradation)  
**Applies to**: Market Data Ingestion Pipeline, Live WebSocket feeds, Factor Scanner

---

## 1. Symptoms & Alerts
- Prometheus alert: `crypto_ingestion_lag_seconds > 60` for more than 2 minutes.
- Scanner API response: `scanner_status = "STALE"` or `data_fresh = false` on core assets (BTC, ETH, SOL).
- Endpoint `/system` or `/health/market-data` reports `market_data_status = "STALE"`.
- Log pattern: `stale_market_data_detected` or `ws_heartbeat_timeout`.

---

## 2. Root Cause Analysis
1. **Exchange WebSocket Hung Connection**: The remote exchange stopped streaming ticks without sending a TCP FIN/RST packet (silent hang).
2. **Rate Limiting**: Ingestion worker exceeded exchange rate limits and was throttled (HTTP 429).
3. **Database Write Bottleneck**: Connection pool saturation or write locks preventing candle persistence.
4. **Network Partition**: Loss of internet connectivity between ingestion container and exchange gateway.

---

## 3. Immediate Triage & Mitigation Steps

### Step 1: Inspect System Health
Query the `/system` endpoint to verify overall state:
```bash
curl -s http://localhost:8000/system | jq .
```
Check `ingestion_lag_seconds` per exchange.

### Step 2: Check Ingestion Worker Logs
```bash
docker compose logs -n 100 -f worker
```
Look for:
- `ws_heartbeat_timeout` (triggered when no message received in 30s)
- `exchange_fallback_triggered`
- `rate_limit_exceeded`

### Step 3: Trigger Failover / Restart Ingestion Service
If a specific exchange feed is hung, restart the ingestion worker container:
```bash
docker compose restart worker
```
The ingestion supervisor will reboot, verify connection to the fallback router, and backfill any missing 1h/5m candles.

### Step 4: Verify Recovery
Check that `/api/v1/scanner/rankings` shows `fresh_count > 0` and `scanner_status == "UP"`:
```bash
curl -s -H "X-API-Key: dev-api-key-researcher-1" http://localhost:8000/api/v1/scanner/rankings | jq '{status: .scanner_status, fresh: .fresh_count, stale: .stale_count}'
```
Ensure `crypto_ingestion_lag_seconds` drops below 15 seconds.
