# Crypto Intelligence, Market Scanner, Backtesting & Paper Trading Platform

A production-quality cryptocurrency market intelligence, quantitative factor scanner, backtesting engine, and paper-trading laboratory built in Python 3.12+.

---

## Key Principles & Architecture

1. **Non-Custodial / Research First**: Operates exclusively in research and paper-trading mode. Live real-money trading is disabled by design.
2. **Multi-Factor Quantitative Engine**: Computes explainable multi-horizon momentum, relative strength vs. benchmarks (BTC/ETH), trend alignment, volume acceleration, realized volatility, and liquidity metrics.
3. **Point-in-Time Bias Mitigation**:
   - **Look-Ahead Bias**: Automated perturbation test suite ensures zero future data leakage.
   - **Survivorship Bias**: Historical universe snapshots preserve delisted assets up to their exact delisting timestamps.
4. **Realistic Execution Simulator**:
   - Never fills orders at naive candle close.
   - Models market-depth slippage, top-of-book bid-ask spread, exchange maker/taker fee tiers, and latency buffers.
5. **Open-Source & Resilient**:
   - Zero mandatory paid API keys.
   - Graceful degradation across CCXT, CoinGecko, DefiLlama, and DexScreener feeds.

---

## Project Structure

```
crypto-intelligence/
├── apps/
│   ├── api/                   # FastAPI async REST API & OpenAPI docs
│   └── dashboard/             # Streamlit quantitative terminal & research UI
├── src/
│   ├── config/                # Pydantic v2 settings & domain enums
│   ├── database/              # SQLAlchemy 2.0 async models (26 tables) & cache
│   ├── ingestion/             # Rate-limited async exchange & aggregator collectors
│   ├── validation/            # Candle integrity & anomaly detection
│   ├── normalization/         # Strict UTC timestamp & symbol normalization
│   ├── features/              # Vectorized Polars/NumPy quantitative factor calculations
│   ├── scoring/               # Multi-factor models (Core, Altcoin, Small-Cap, Meme)
│   ├── risk/                  # Portfolio exposure, drawdown limits & sizing
│   ├── backtesting/           # Bias-protected simulation & walk-forward validator
│   ├── paper/                 # Virtual broker, order routing, portfolio accounting
│   ├── meme/                  # Meme radar, DEX liquidity & risk flags
│   ├── alerts/                # Webhook alert dispatcher & monitors
│   └── utils/                 # Structured logging, math, time helpers
├── tests/                     # Unit, bias-leakage, and integration test suites
├── configs/                   # YAML configs for scoring weights & risk limits
├── docker/                    # Dockerfiles & container configs
└── docker-compose.yml         # TimescaleDB, Redis, API, Dashboard & Worker
```

---

## Quickstart

### 1. Local Environment Setup

```bash
# Clone and enter workspace
git clone <repo_url>
cd crypto-intelligence

# Install dependencies
pip install -e ".[dev]"
```

### 2. Run Test Suite

```bash
pytest tests/ -v
```

### 3. Start API Locally

```bash
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
# View interactive API docs at http://localhost:8000/docs
# Check health at http://localhost:8000/health
```

### 4. Start Dashboard Locally

```bash
streamlit run apps/dashboard/app.py --server.port 8501
# View UI at http://localhost:8501
```

### 5. Run with Docker Compose

```bash
docker compose up -d
```
