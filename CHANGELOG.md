# Changelog

All notable changes to the Crypto Intelligence Platform are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [3.0.0] - 2026-10-04

### Added
- **Next.js 15 Quantitative Workstation (`apps/web`)**: Complete ground-up rebuild featuring App Router, strict TypeScript, TanStack Virtual tables rendering 500+ assets at 60fps, TradingView Lightweight Charts, Apache ECharts, command palette (`Ctrl+K`), and dark-first high-density design.
- **Real-Time Reactive Streaming**: Redis Pub/Sub powered Server-Sent Events (`/stream/scanner`, `/stream/prices`, `/stream/alerts`) with cell flash animations and `Last-Event-ID` reconnection.
- **Product Features (Phase 8)**:
  - Multi-channel alert dispatchers (`TelegramAlertDispatcher`, `EmailAlertDispatcher`, `DiscordAlertDispatcher`) with quiet hours and in-app inbox.
  - Watchlist endpoints (`/api/v1/watchlist`) with custom asset tags and trade journal notes on paper orders.
  - Multi-asset correlation heatmap (`/api/v1/analytics/correlation`) and macro stress testing scenarios (`/api/v1/analytics/portfolio-stress`).
  - Sector concentration and Herfindahl-Hirschman Index (HHI) analysis (`/api/v1/analytics/sector-exposure`).
  - In-Sample / Out-of-Sample parameter sweep grid search (`/api/v1/backtests/sweep`) with overfit warnings.
  - Self-contained printable HTML backtest audit report export (`/api/v1/backtests/{id}/report`).
- **Research Integrity & Validity (Phase 6)**:
  - Forward-return attribution engine measuring Information Coefficient (Pearson & Spearman), hit rate, and decile returns.
  - Statistical robustness metrics including Deflated Sharpe Ratio (DSR) and bootstrap confidence intervals.
  - Point-in-time universe snapshots eliminating survivorship bias.
- **Container Infrastructure & Routing (Phase 5 & 9)**:
  - Multi-stage unprivileged `docker/Dockerfile.web` for Next.js workstation.
  - Caddy reverse proxy (`docker/Caddyfile`) with automatic compression, security headers, and SSE relay.
  - Automated CI test suite running look-ahead audits, integration tests, and 11 modernized Jupyter research notebooks.

### Changed
- **Backtesting Execution Engine (Phase 1)**:
  - Enforced strict $t+1$ execution order queuing to completely eliminate same-bar look-ahead bias.
  - Bracket gap fills handling when candles open beyond stops (`min(open, stop_price)` for longs).
  - Realistic execution modeling incorporating Corwin-Schultz spread proxy and square-root market impact slippage.
  - $O(1)$ timestamp indexing delivering ~8x backtest speedup on large multi-asset datasets.
  - Accurate annualization derived directly from data timeframe (hourly = 8760, daily = 365).
- **Paper Trading Brokerage (Phase 2)**:
  - Replaced floating-point money with arbitrary-precision `Numeric(28, 10)` and `Decimal` arithmetic.
  - Exact symbol resolution joining `Market.id` to prevent token symbol collisions (e.g. BTC vs WBTC).
  - Enforced resting limit and stop order evaluation against intrabar extremes.
- **Market Data Ingestion (Phase 3)**:
  - Hardened with exponential backoff and jitter (`tenacity`), respecting HTTP 429 Retry-After headers.
  - Automatic per-exchange circuit breaker failover (`Binance → Coinbase → Kraken`).
  - Multi-venue consensus price deviation checks and stablecoin depeg detection.
- **Retired Legacy Prototype**:
  - Deprecated Streamlit prototype in `apps/dashboard` and removed `docker/Dockerfile.dashboard`.

### Fixed
- **DEFECT-1 through DEFECT-15**: Eliminated all synthetic candle fallbacks, hardcoded baseline prices (`?? 64000`), fake alerts, and synthetic deltas (`+5.2%`).
- **Idempotency**: Prevented duplicate order submissions via unique database constraint on `idempotency_key`.
- **API Error Formatting**: Standardized error responses to RFC 7807 `problem+json` format with request tracing IDs.
- **Database Concurrency**: Fixed composite primary key merges on `OHLCV` tables for idempotent pipeline runs.

### Security
- **Hardened Invariant 1**: Guaranteed `LIVE_TRADING_ENABLED=False` hardcoded at Pydantic validator, settings, and gateway levels.
- **Authentication & Rate Limiting**: All non-health API endpoints protected by Bearer token / API key authentication.
- **CORS Allow-List**: Strict origin filtering with credentials protection.
- **Immutable Audit Trail**: Append-only `LedgerEvent` table with database-level update/delete prevention.
- **Container Hardening**: All Docker containers executed with unprivileged non-root users (`nextjs`, `appuser`).
