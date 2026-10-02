# 🏦 Crypto Intelligence Platform v2.0

> **REAL MARKET DATA → VALIDATED STORAGE → REAL-TIME FEATURES → LIVE SCANNER → EXPLAINABLE SIGNAL → DEMO ORDER → REALISTIC SIMULATED FILL → PORTFOLIO ACCOUNTING → LIVE P&L → RESEARCH MEASUREMENT**

A Python-first cryptocurrency intelligence platform built for **research integrity and data provenance** — not for simulating a convincing trading terminal.

---

## ⚡ What's New in v2.0

| Category | Change |
|---|---|
| **Data Integrity** | All 8 synthetic fallback paths removed. Missing data raises explicit errors. |
| **DataMode System** | `LIVE / HISTORICAL / SYNTHETIC_TEST / REPLAY` — always visible in the UI |
| **Live Market Data** | CCXTProvider fetches real OHLCV from Binance (or any CCXT exchange) |
| **Live Ingestion** | Continuous ingestor loop with per-asset provenance and staleness tracking |
| **Live Scanner** | ScannerSnapshot rows written per cycle — enables forward return attribution |
| **Dynamic Universe** | Volume/liquidity-qualified asset discovery (not a hardcoded 8-asset list) |
| **Idempotent Orders** | `idempotency_key` on PaperOrder prevents duplicate submission |
| **CORS Security** | Restricted to `CORS_ALLOWED_ORIGINS` allow-list; `allow_credentials=False` |
| **Audit Ledger** | `LedgerEvent` table for immutable paper trading audit trail |
| **API v2.0** | `/health/versions`, `/health/market-data`, `/api/v1/scanner/*` endpoints |
| **Regression Tests** | 13 tests ensure synthetic fallbacks can never be re-introduced |

---

## 🏗 Architecture

```
Exchange (Binance/Kraken/Coinbase)
    │
    ▼  CCXTProvider.fetch_ohlcv()
OHLCVValidator  ──────────────────────── DataQualityStatus (GOOD/STALE/ANOMALOUS)
    │
    ▼  ingest_candles_for_asset()
OHLCV table  ─────────────────────────── market_id + timeframe + validation_status
    │
    ▼  calculate_and_store_asset_features()
Feature table  ───────────────────────── momentum, RS, EMA ratios, ADX, RVOL
    │
    ▼  score_universe()
Score table  ─────────────────────────── opportunity_score, risk_flags, breakdown_json
    │
    ▼  LiveScannerPipeline.run_scan_cycle()
ScannerSnapshot  ─────────────────────── rank, price_at_snapshot, data_fresh, data_age_seconds
    │
    ▼  Dashboard / API
User sees: real scores + freshness indicators + data mode banner
```

**Non-custodial. No real-money trading. `LIVE_TRADING_ENABLED` is permanently `False` at the Pydantic validator level.**

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
# Editable install with dev and research dependencies
pip install -e ".[dev,research]"
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env:
#   DATA_MODE=LIVE
#   DATABASE_URL=sqlite+aiosqlite:///./crypto_intelligence.db
#   DEFAULT_EXCHANGE=binance
```

### 3. Run one-time market data ingestion

```bash
python -m src.ingestion.live_ingestor
```

### 4. Start the dashboard

```bash
streamlit run apps/dashboard/app.py
```

### 5. (Optional) Start the API

```bash
python -m apps.api.main
# Docs: http://localhost:8000/docs
```

### 6. (Optional) Run the continuous scanner

```bash
python -m src.scanner.pipeline
```

---

## 📁 Project Structure

```
CRYPTO-/
├── apps/
│   ├── api/
│   │   ├── main.py                    # FastAPI app factory — v2.0 CORS + guards
│   │   └── routes/
│   │       ├── health.py              # /health, /health/versions, /health/market-data
│   │       ├── scanner.py             # /api/v1/scanner/rankings, /status, /snapshots
│   │       ├── paper.py               # Paper trading broker endpoints
│   │       └── ...
│   └── dashboard/
│       ├── app.py                     # Streamlit UI — DATA_MODE banner + no-data states
│       └── data_layer.py              # v2.0: no synthetic candles, no fake alerts
│
├── src/
│   ├── config/
│   │   ├── settings.py                # DataMode, LIVE_TRADING_ENABLED=False (enforced)
│   │   ├── constants.py               # DataMode, DataQualityStatus, LedgerEventType enums
│   │   └── exceptions.py             # DataUnavailableError, PriceUnavailableError hierarchy
│   ├── database/
│   │   └── models/
│   │       ├── ledger.py              # LedgerEvent — immutable audit log (NEW)
│   │       └── scanner.py             # ScannerSnapshot, UniverseSnapshot (NEW)
│   ├── ingestion/
│   │   ├── providers/
│   │   │   ├── base.py                # MarketDataProvider Protocol + RawCandle/RawTicker
│   │   │   ├── ccxt_provider.py       # CCXT live market data (no synthetic fallback)
│   │   │   └── dexscreener_provider.py # DEX data (raises on failure, no mock)
│   │   ├── live_ingestor.py           # Continuous ingestion loop with provenance (NEW)
│   │   └── universe.py               # Dynamic universe discovery (NEW)
│   ├── scanner/
│   │   └── pipeline.py               # LiveScannerPipeline + ScannerSnapshot writer (NEW)
│   └── paper/
│       ├── broker.py                  # v2.0: idempotency, real prices only
│       └── models.py                  # idempotency_key, price_stale fields
│
└── tests/
    └── regression/
        └── test_v2_synthetic_fallback_regression.py  # 13 tests — all passing
```

---

## 🔐 Data Integrity Guarantees (v2.0)

| Rule | Enforcement |
|---|---|
| No synthetic OHLCV candles | `ensure_seeded_data()` no longer generates candles |
| No hardcoded price fallbacks | `PriceUnavailableError` raised — never `return 64200.0` |
| No mock DexScreener data | `ExternalProviderUnavailableError` raised — `_get_fallback_pairs()` removed |
| No fabricated alerts | `get_recent_alerts()` returns `[]` if DB is empty |
| No duplicate orders | `idempotency_key` unique constraint on `paper_orders` |
| No live trading | `LIVE_TRADING_ENABLED` Pydantic validator raises `ValueError` if `True` |
| No wildcard CORS | `allow_origins=settings.cors_allowed_origins_list`, `allow_credentials=False` |

All rules are enforced by **regression tests** that fail if any synthetic fallback is re-introduced.

---

## 🧪 Running Tests

```bash
# Regression suite (13 tests — all synthetic fallback guards)
python -m pytest tests/regression/ -v

# Full test suite
python -m pytest tests/ -v
```

---

## 📡 API Endpoints (v2.0)

| Method | Path | Description |
|---|---|---|
| GET | `/health` | System health + data_mode + live_trading_enabled |
| GET | `/health/versions` | All component version strings |
| GET | `/health/market-data` | Per-asset staleness status |
| GET | `/api/v1/scanner/rankings` | Live rankings with data_fresh per asset |
| GET | `/api/v1/scanner/status` | Scanner operational state |
| GET | `/api/v1/scanner/snapshots` | Historical snapshot records |
| GET | `/api/v1/assets/` | Asset universe |
| GET | `/api/v1/scores/` | Latest scores |
| POST | `/api/v1/paper/orders` | Place paper order (with idempotency_key) |
| GET | `/api/v1/paper/portfolio/{account_id}` | Portfolio summary |
| GET | `/docs` | Swagger UI |

---

## ⚙️ Configuration

Key `.env` variables:

```env
# Data mode — always visible in dashboard banner
DATA_MODE=LIVE          # LIVE | HISTORICAL | SYNTHETIC_TEST | REPLAY

# Architecture guard — DO NOT change to true
LIVE_TRADING_ENABLED=false

# Exchange
DEFAULT_EXCHANGE=binance

# CORS — comma-separated, no wildcards in production
CORS_ALLOWED_ORIGINS=http://localhost:8501

# Staleness thresholds (seconds)
MARKET_DATA_STALE_THRESHOLD_SECONDS=60
SCANNER_STALE_THRESHOLD_SECONDS=120
PRICE_STALE_THRESHOLD_SECONDS=300
```

---

## 📜 License

MIT — Research and education use only. Not financial advice.
