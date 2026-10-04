# 🏦 Crypto Intelligence Platform v3.0

> **QUANTITATIVE CRYPTO RESEARCH & PAPER-TRADING WORKSTATION**
> 
> *Multi-Factor Statistical Models • Look-Ahead-Free Backtesting • Double-Entry Paper Ledger • Real-Time SSE Diff Streaming • Dense Next.js 15 Workstation*

[![CI Pipeline](https://github.com/MuthuvelMukesh/CRYPTO-/actions/workflows/ci.yml/badge.svg)](https://github.com/MuthuvelMukesh/CRYPTO-/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## ⚡ What's New in v3.0

| Domain | Major Upgrade |
|---|---|
| **Frontend Workstation** | Next.js 15 App Router (`apps/web`) replacing legacy Streamlit with TanStack Virtual (500+ assets @ 60fps), TradingView Lightweight Charts, Apache ECharts, and responsive dark-first design. |
| **Backtest Correctness** | Rigorous $t+1$ execution eliminating same-bar look-ahead bias; bracket gap handling ($O \le \text{stop}$); Corwin-Schultz bid-ask & square-root market impact slippage; $O(1)$ timestamp indexing; real walk-forward validation with Deflated Sharpe Ratios. |
| **Paper Ledger & Risk** | Double-entry append-only `LedgerEvent` with database triggers; arbitrary-precision `Numeric(28, 10)` monetary arithmetic; exact symbol resolution (`Market.id` joining); resting limit order execution; idempotency keys. |
| **Ingestion Resilience** | Exponential backoff with jitter (`tenacity`), 429/Retry-After respect, per-exchange circuit breaker failover (`Binance → Coinbase → Kraken`), multi-venue consensus price deviation checks, and token depeg detection. |
| **API & Streaming** | FastAPI v3 with API key / Bearer authentication, server-side pagination, RFC 7807 `problem+json` error contracts, async backtest background jobs, and real-time Server-Sent Events (`/stream/scanner`, `/stream/prices`, `/stream/alerts`). |
| **Product Features** | Multi-channel alert delivery (Telegram, Email, Discord) with quiet hours & in-app inbox; watchlists with custom tags and trade journal notes; Asset Compare matrix & macro stress testing (`BTC −20%`, Crypto Winter, etc.); In-Sample / Out-of-Sample parameter sweep heatmaps; self-contained HTML audit report exports. |
| **Research Validity** | Point-in-time forward return attribution (1d/7d/30d), Information Coefficient (Pearson & Spearman), mean decile returns, bootstrap confidence intervals, and Deflated Sharpe Ratios. |

---

## 🏗 Target Architecture

```
Browser (React 19, TanStack Virtual, TradingView Lightweight Charts, Apache ECharts)
   │ HTTPS + SSE
Next.js 15 (App Router, BFF at port 3000) ── Server Components, Route Handlers, Proxy Relay
   │ Internal Network
Caddy Reverse Proxy (:80 / :443) ── Compression, Security Headers, Route Dispatch
   ├── /api/*, /health*, /stream/* ──▶ FastAPI v3 Backend (:8000)
   └── /*                          ──▶ Next.js Web Container (:3000)
                                            │
                                            ▼
FastAPI v3 (Auth, Rate Limits, Jobs, SSE) ── Postgres / TimescaleDB ── Worker (Scheduler & Ingest)
                     └──────────── Redis 7 (Pub/Sub, Heartbeat, Cache) ────────┘
```

---

## 🛡️ Core Regulatory Invariants (Non-Negotiable)

1. **Strictly Non-Custodial & Paper Trading Only:** `LIVE_TRADING_ENABLED=False` is hardcoded at the Pydantic validator, settings, and execution gateway levels. No real-order execution or wallet inputs exist.
2. **No Fabricated Data:** Missing values strictly format to em-dash (`—`) with an explicit reason. No silent baseline prices (`?? 64000`) or fabricated deltas (`+5.2%`).
3. **Persistent Data Mode Visibility:** Active data mode tag (`LIVE`, `HISTORICAL`, `SYNTHETIC_TEST`, `REPLAY`) is stamped in all API payloads and displayed in the UI top bar.
4. **No Look-Ahead:** Signals computed at bar $t$ close are strictly filled at bar $t+1$ open or later.
5. **Double-Entry Ledger Integrity:** All paper trading orders, fills, and cash mutations write immutable ledger events with scheduled reconciliation drills.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.12+
- Node.js 20+ (for Next.js workstation)
- Docker & Docker Compose (for containerized stack)

### 2. Local Python Environment Setup

```bash
# Clone repository
git clone https://github.com/MuthuvelMukesh/CRYPTO-.git
cd CRYPTO-

# Install editable package with dev and research extras
pip install -e ".[dev,research]"

# Configure environment variables
cp .env.example .env
```

### 3. Running the Stack via Docker Compose

```bash
# Start TimescaleDB, Redis, API, Worker, Next.js Web Workstation, and Caddy
docker compose up -d

# Verify service health
docker compose ps
```

- **Quantitative Workstation (Web UI):** [http://localhost](http://localhost) or [http://localhost:3000](http://localhost:3000)
- **FastAPI Documentation (Swagger):** [http://localhost/docs](http://localhost/docs) or [http://localhost:8000/docs](http://localhost:8000/docs)
- **System Health & Telemetry:** [http://localhost:8000/system](http://localhost:8000/system)

### 4. Running Locally in Development Mode

```bash
# Terminal 1: Start FastAPI backend
python -m apps.api.main

# Terminal 2: Start Ingestion & Factor Worker
python -m src.scanner.pipeline

# Terminal 3: Start Next.js Frontend Workstation
cd apps/web
npm install
npm run dev
# Workstation running at http://localhost:3000
```

---

## 🧪 Comprehensive Test Suite

All 182+ automated backend, integration, and regression tests pass cleanly:

```bash
# Run complete test suite (unit, integration, regression, bias, notebooks)
pytest -v

# Run look-ahead bias audit
pytest tests/bias/ -v

# Run research notebooks execution verification
pytest tests/integration/test_notebooks.py -v

# Run static analysis and linting
ruff check .
mypy src apps
```

---

## 📁 Repository Layout

```
CRYPTO-/
├── apps/
│   ├── api/                           # FastAPI v3 Backend
│   │   ├── main.py                    # Application factory, middleware & lifespan
│   │   ├── deps.py                    # Auth, DB, Redis, and Rate-limiting dependencies
│   │   └── routes/                    # REST routes (scanner, assets, paper, backtest, analytics, alerts)
│   └── web/                           # Next.js 15 Production Workstation
│       ├── src/app/(dash)/            # Workstation pages (Scanner, Assets, Portfolio, Backtests, etc.)
│       ├── src/components/            # Domain components, charts, and virtualized tables
│       └── src/lib/api/               # Generated OpenAPI client and typed fetchers
│
├── src/
│   ├── alerts/                        # Multi-channel alert engine (Telegram, Discord, Email)
│   ├── backtesting/                   # Look-ahead-free engine, metrics, strategies, parameter sweep
│   ├── config/                        # Settings, Invariant guards, and custom exceptions
│   ├── database/                      # SQLAlchemy 2 models, Timescale migrations, and sessions
│   ├── features/                      # Vectorized momentum, trend, relative strength, volume, and regime
│   ├── ingestion/                     # CCXT providers, fallback failover, and consensus verification
│   ├── paper/                         # Virtual brokerage, double-entry ledger, and risk engine
│   ├── research/                      # Walk-forward validation, IC calculation, and ML models
│   ├── scanner/                       # Live universe qualification and point-in-time snapshot writer
│   └── scoring/                       # Explainable multi-factor scorers (Core, Altcoin, SmallCap, Meme)
│
├── docker/                            # Dockerfile.api, Dockerfile.worker, Dockerfile.web, Caddyfile
├── docs/                              # Architecture specification, runbooks, and baselines
├── notebooks/                         # 11 Modernized and CI-tested Jupyter research notebooks
└── tests/                             # Unit, integration, bias, and regression test suites
```

---

## 📜 Regulatory Notice & License

This software is provided for academic, quantitative research, and paper-trading simulation purposes only. It is **not financial advice**, does not support real-money order routing, and makes no claims of trading profitability.

Licensed under the **[MIT License](LICENSE)**.
