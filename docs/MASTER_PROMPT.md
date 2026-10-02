<USER_REQUEST>
# UNIFIED MASTER PROMPT — Crypto Intelligence Platform v2.0 → v3.0

One prompt covering backend correctness, platform hardening, research validity, and the Next.js UI rebuild. Paste everything below the divider into your coding agent (Claude Code, Cursor, etc.) from the repo root.

---

## 0. ROLE

You are a senior staff engineer (quant platform, Python backend, TypeScript frontend, product design) upgrading **Crypto Intelligence Platform v2.0** to **v3.0**. The product is a **crypto research and paper-trading workstation**: dense, fast, trustworthy, dark-first. It is **not** a live trading system and must never become one.

You work incrementally, test-first, in small reviewable commits. You do not rewrite things that work. You do not guess: when unsure, read the code, run it, or ask.

## 1. REPOSITORY CONTEXT

- Python 3.12, FastAPI, SQLAlchemy 2 async (Postgres/Timescale in Docker, SQLite for dev), Redis, CCXT, Polars/Pandas/NumPy, structlog, pytest (asyncio_mode=auto).
- Layout: `apps/api` (FastAPI), `apps/dashboard` (Streamlit, to be replaced), `src/{alerts,backtesting,config,database,features,ingestion,paper,research,scanner,scoring,utils,validation}`, `tests/{unit,integration,bias,regression}`, `notebooks/`, `docker/`, `docs/architecture/ARCHITECTURE_SPEC.md`.
- Pipeline: CCXT → OHLCVValidator → OHLCV table → features → scores → ScannerSnapshot → API/UI → PaperBroker → LedgerEvent.
- Target architecture:

```
Browser (React, TanStack Query, Lightweight Charts)
   │ HTTPS + SSE
Next.js (App Router, BFF)  ── server components, route handlers (proxy + SSE relay), session middleware
   │
FastAPI v3 (auth, rate limits, jobs, SSE) ── Postgres/Timescale ── Worker (scheduler, ingest, features, scores, scan)
                    └──────────── Redis (pub/sub, cache, locks, heartbeat) ────────────┘
```

## 2. INVARIANTS (NEVER VIOLATE)

1. **No live trading.** Do not weaken `LIVE_TRADING_ENABLED` enforcement (settings validator, startup check, `LiveExecutionGateway`). No code path sends orders to a real exchange. Exchange access is read-only market data. The UI has no real-order wording, no wallet, no exchange API-key inputs, and shows "Paper trading only" wherever orders appear.
2. **No fabricated data.** Never add synthetic candles, hardcoded prices, fake deltas, placeholder scores, or silent defaults that look like real data, in backend **or** frontend. Missing data → `null` / explicit error / visible "no data" state (`—` with a reason). Test fixtures live only in test directories (`tests/`, `__fixtures__/`, MSW handlers) and are never imported by app code.
3. **Data mode is always visible** (LIVE / HISTORICAL / SYNTHETIC_TEST / REPLAY) in API responses and in the UI top bar. SYNTHETIC_TEST shows a persistent warning banner.
4. **Existing regression tests stay green** (`tests/regression/test_v2_synthetic_fallback_regression.py`). If one must change, explain why.
5. **No look-ahead.** A decision using information available at time *t* may only be filled at *t+1* or later.
6. **Secrets never in git or in client bundles.** Environment variables and `.env.example` placeholders only. The browser talks only to Next.js; Next.js proxies to FastAPI and attaches credentials server-side.
7. **Backwards-safe migrations.** Every schema change goes through Alembic with upgrade and downgrade.
8. **Every number has context:** units, timeframe and freshness are discoverable. Persistent footer in the UI: "Research and paper trading only. Not financial advice."

## 3. WORKING RULES

- Work in **phases** (section 5). Finish a phase (code, tests, docs, green CI) before starting the next. One branch per phase: `v3/phase-N-short-name`. Conventional commits.
- **Test-first for bugs:** write a failing test that reproduces the defect, then fix it.
- Read a file before editing it. Reproduce before claiming broken. Run the test before claiming fixed.
- Focused diffs. No drive-by refactors or formatting churn outside touched files.
- Type hints everywhere in new Python; strict TypeScript in the frontend; keep ruff, mypy, ESLint, and `tsc --noEmit` clean on touched files.
- If a requirement conflicts with an invariant, the invariant wins; say so.
- **Ask before proceeding** if a change alters public API contracts, drops data, changes primary keys, or needs a new paid external service. If a backend endpoint the UI needs is missing, **build the endpoint first (with tests)**; never fake data in the UI.
- After each phase, deliver a **Phase Report** (section 8) and stop for my approval before continuing.
- **Sequencing rule:** do not start the frontend (Phase 7) until Phases 1–4 are merged. The UI must not be built on an incorrect backtester or an unauthenticated API.

## 4. FIRST ACTIONS (before any change)

1. `pip install -e ".[dev]"`, then `pytest -q`. Record pass/fail counts as the **baseline**. Do not trust claims like "13 tests all passing" until you have run them.
2. Run `ruff check .` and `mypy src apps`; record the baseline.
3. `.env.example` appears mis-encoded or binary. Recreate it as UTF-8 without BOM.
4. Write `docs/V3_BASELINE.md`: test results, lint results, everything that fails on a clean checkout.

---

## 5. PHASES

### PHASE 0 — Install, packaging, safety net
- Add `scikit-learn` (imported by `src/research/ml_models.py`, missing from `pyproject.toml`). Put research-only deps in an optional `research` extra; `ml_models` should fail with a clear message if it's missing.
- Fix README install steps (there is no `requirements.txt`; use `pip install -e ".[dev]"` or generate a lock file with `uv`/`pip-tools`).
- GitHub Actions CI: ruff, mypy, pytest + coverage (threshold = current baseline, then ratchet), `pip-audit`, gitleaks. Add `pre-commit` and a `LICENSE` matching the MIT declaration.
- docker-compose: remove obsolete `version:`, pin image tags (no `latest`).

**Acceptance:** fresh clone → install → `pytest` runs; CI green on a PR.

### PHASE 1 — Backtest correctness (highest priority)
Files: `src/backtesting/{engine,execution,metrics,walk_forward}.py`, `strategies/*`.
1. **Same-bar look-ahead.** Currently the strategy gets bar *t* close-based features and fills at bar *t*'s open. Signals computed at the close of *t* must be queued and filled at the open of *t+1*. Add a test in `tests/bias/` that perturbs bar *t*'s own close/high/low/features and asserts fills at *t* don't depend on them (it must fail on the old code). Keep the existing future-perturbation test.
2. **Bracket gap handling.** In `check_bracket_triggers`, if the bar opens beyond the stop, fill at the open: stop fill = `min(open, stop_price)` for longs; take-profit fill = `max(open, tp_price)`. Document the intrabar ordering assumption (stop first) and make it configurable.
3. **Remove hardcoded engine fallbacks.** No exit at `entry_price * 0.5` for delistings, no default `volume_usd` of 500000/100000. Raise a clear error, or mark the trade `low_confidence=True` with a reason surfaced in results and metrics.
4. **Use the spread estimator** (`estimate_spread_bps`, `spread_est_bps`, `atr_14_pct`) in fills when available.
5. **Performance.** Step C scans all of `candle_lookup` each bar (≈ O(bars² × assets)). Pre-index by timestamp. Add a benchmark (e.g., 50 assets × 2 years of 1h bars) and record before/after.
6. **Annualization.** `periods_per_year` defaults to 365. Derive it from the data's timeframe (1h → 8760) for Sharpe, Sortino, volatility. Unit tests for hourly and daily.
7. **Walk-forward.** Make it real (non-overlapping train/test, in-sample parameter search, out-of-sample evaluation, per-window parameters and metrics) or rename it. Stop using a CAGR ratio across regimes as the only "efficiency" signal; add Sharpe and drawdown comparisons.
8. **Cost stress test** helper: re-run at 1x/2x/3x fees and slippage and return a table.

**Acceptance:** new look-ahead test fails on old code and passes on new; all bias tests pass; benchmark shows a clear speedup; hourly annualization tested.

### PHASE 2 — Paper trading accounting and risk
Files: `src/paper/*`, `src/database/models/{paper,ledger}.py`, `src/config/settings.py`.
1. **Decimal money.** Replace `Float` with `Numeric(28,10)` / `Decimal` for balances, quantities, prices, fees in accounts, orders, fills, positions, ledger. Alembic migration with data conversion and downgrade.
2. **Exact price lookup.** `PaperBroker.get_latest_price` uses `OHLCV.market_id.like(f"%{symbol}%")` (BTC can match WBTC, ETH can match WETH/STETH). Resolve to an exact `market_id` (exchange + pair + timeframe). Tests with colliding symbols.
3. **Wire configured risk limits.** `Settings` (15% position, 12 positions, 15% drawdown) is not what `RiskEngine()` enforces (its own defaults of 25%, 15, 20%). Build `RiskEngine` from injected settings; test that settings values are the enforced ones.
4. **Ledger integrity.** Make `ledger_events` append-only at DB level (trigger or revoked UPDATE/DELETE). Add a reconciliation job that replays the ledger and compares to cash, positions and fills; on mismatch raise an alert and fail the health check. Test a tampered row is detected.
5. **Order realism (incremental).** LIMIT and STOP orders as resting orders evaluated on each new candle; optional book-walking fills with partial fills from `OrderbookSnapshot`. MARKET stays default. All idempotent via `idempotency_key`.
6. Remove module-level `settings = get_settings()` in `broker.py`; inject settings.

**Acceptance:** concurrency test shows no duplicate orders per idempotency key; reconciliation passes after a randomized order sequence; symbol-collision tests pass.

### PHASE 3 — Data reliability
Files: `src/ingestion/*`, `src/validation/*`, `src/database/*`.
1. **Retry + circuit breaker** in `CCXTProvider` and the CoinGecko/DexScreener providers: exponential backoff with jitter (`tenacity`), respect 429/Retry-After, per-exchange circuit breaker, configurable fallback exchanges. (The architecture doc promises this; the code only sets `enableRateLimit`.)
2. **Gap detection and backfill:** find missing candles per market/timeframe, backfill, record incomplete ranges so features refuse to compute across holes (or flag results).
3. **Consensus price check** across at least two venues; flag deviations beyond a threshold as ANOMALOUS and exclude from scoring.
4. **Stablecoin and wrapped-asset handling:** depeg detection; symbol alias/migration table so renamed tokens keep history.
5. **Feature and score versioning:** store `FEATURE_VERSION` / `SCORING_VERSION` per row for reproducibility.
6. **Scheduler:** replace `asyncio.sleep` loops with APScheduler or Arq plus distributed locks; worker heartbeat in Redis.
7. **Timezone hygiene:** timezone-aware UTC at all boundaries; replace blind `.replace(tzinfo=UTC)` with explicit normalization and tests.
8. Configurable exchange per deployment, with a startup connectivity check and a clear error for geo-restricted exchanges.

**Acceptance:** recorded-response (VCR-style) tests cover timeouts, 429s, bad ticks and gaps; ingestion survives injected failures without crashing or writing bad data.

### PHASE 4 — API hardening and contract (the UI's foundation)
Files: `apps/api/*`.
1. **Authentication** on every non-health route (API key or JWT; ask me which) plus rate limiting. Mutating endpoints also require CSRF protection for browser sessions.
2. **Fail fast on startup.** `lifespan` currently swallows DB init errors. Fail or report unhealthy on invalid DB/settings. Reject default or weak secrets when `ENVIRONMENT=production`.
3. **Move all `apps/dashboard/data_layer.py` queries into API endpoints.** The scanner endpoint uses **one query** (latest feature/price per asset via window function or lateral join), not two per asset. Return `data_fresh`, `data_age_seconds`, score breakdown and penalties, and `null` (never fake values) for missing data.
4. **Pagination, filtering, sorting** server-side for scanner, trades, snapshots, alerts.
5. **Backtests as async jobs:** `POST /api/v1/backtests` → job id; status and progress endpoint; cancel; results persisted with code version, config hash and data hash. Cap parameters (date range, symbols).
6. **SSE streams** from Redis pub/sub: `/stream/scanner`, `/stream/prices?symbols=`, `/stream/alerts`. Throttled, diff-based, with `Last-Event-ID` resume.
7. **Consistent errors** (RFC 7807 problem+json) and request IDs in logs.
8. Publish a stable OpenAPI schema; CI fails on breaking changes.

Endpoints the UI will need: scanner rankings; asset detail + candles + features + score history; regime; portfolio/orders/fills/ledger; backtest jobs (create/status/results/compare); alerts + rules; research attribution; system health + versions; SSE streams.

**Acceptance:** unauthenticated requests get 401; scanner endpoint issues a constant number of queries regardless of universe size (asserted in a test); backtest job lifecycle covered by integration tests.

### PHASE 5 — Platform and operations
- Alembic baseline migration; Timescale hypertables, compression, retention for OHLCV/trades/orderbook.
- Docker: no hardcoded DB password in compose (env/secret files), do not publish Postgres/Redis ports to the host by default, non-root users, healthchecks for api/worker/web, pinned images, reverse proxy (Caddy or nginx) with HTTPS.
- Observability: Prometheus metrics (ingestion lag per exchange, scan duration, API latency, job queue depth, ledger reconciliation status), structured logs with request IDs, a `/system` health summary.
- Backups: scheduled Postgres backups plus a **tested restore**. Runbooks in `docs/runbooks/` (stale data, exchange outage, ledger mismatch).

**Acceptance:** `docker compose up` brings all services healthy from a clean machine using only `.env`; restore drill documented and executed once.

### PHASE 6 — Research validity
Files: `src/scoring/*`, `src/research/*`, `src/scanner/*`.
1. **Forward-return attribution** from `ScannerSnapshot` (point-in-time safe): forward returns at 1d/7d/30d, information coefficient (Pearson and Spearman), hit rate, mean return by score decile, with sample sizes. Exposed via API.
2. **Statistical robustness:** bootstrap confidence intervals, Deflated Sharpe Ratio, and a counter of strategy variants evaluated.
3. **Scoring hygiene:** no silent flat baselines (e.g., fundamentals = 65). If an input is missing, redistribute weights and attach a `partial_data` flag visible in API and UI. Winsorize before normalization. Weights configurable and versioned.
4. **Position sizing options:** volatility targeting and fractional Kelly as pluggable sizers, with a portfolio volatility cap.
5. **Regime-split reporting** for backtests.
6. `ml_models.py` stays experimental: leakage-safe time-series splits only; no model score feeds production ranking until it beats the baseline out-of-sample in the attribution report.

**Acceptance:** attribution runs on stored snapshots and is tested on a synthetic dataset with known IC (SYNTHETIC_TEST mode, clearly labeled).

---

### PHASE 7 — Next.js frontend (strangler rebuild; start only after Phases 1–4 merge)

Replace Streamlit page by page. Keep Streamlit running until each page has parity.

**7.1 Stack (fixed unless I approve a change)**
- Next.js App Router, React, strict TypeScript (`noUncheckedIndexedAccess`), Tailwind + shadcn/ui (Radix), `lucide-react`.
- TanStack Query, TanStack Table + Virtual, TradingView Lightweight Charts (candles), Apache ECharts (radar, heatmap, waterfall, sector rotation, equity/drawdown).
- React Hook Form + Zod, Zustand (UI-only state), `nuqs` or equivalent for URL state.
- `openapi-typescript` + `openapi-fetch` generated from FastAPI's OpenAPI (`pnpm gen:api`).
- Auth.js or a signed httpOnly cookie session (ask me; default single-user credentials login).
- Vitest + React Testing Library, Playwright, axe-core, MSW (test-only). pnpm, ESLint, Prettier.
- **CI rule:** lint/grep fails the build on numeric display fallbacks (e.g., `?? 64000`, `|| 3400`, `"+5.2%"`). Fallbacks must be `null` → `—`.

**7.2 Layout**
```
apps/web/src/
  app/(auth)/login/
  app/(dash)/{layout.tsx, overview, scanner, assets/[symbol], portfolio, backtests, backtests/[id], memes, sectors, alerts, research, system, settings}
  app/api/                 # BFF route handlers: proxy + SSE relay
  components/shell/        # Sidebar, TopBar, DataModeBanner, StatusBar, CommandPalette
  components/data/         # DataTable, ScoreBadge, FreshnessDot, DeltaCell, Sparkline, EmptyState, ErrorState, Skeletons
  components/charts/       # CandleChart, EquityChart, DrawdownChart, RadarChart, WaterfallChart, Heatmap, SectorRotation
  components/domain/       # ExplainPanel, OrderTicket, RiskCheckList, TradeTable, RegimeBadge
  lib/{api,format,sse,auth}/  hooks/  styles/tokens.css
apps/web/e2e/  apps/web/__fixtures__/
```

**7.3 Design system**
- Principles: dense but calm; scan-first; trust through transparency; no decoration that carries no information.
- Tokens (CSS variables; dark default + light): surfaces, text (muted text must meet WCAG AA 4.5:1), semantic positive/negative/warning/info/accent, distinct regime colors, radius 6/10/14, 4px spacing base.
- Typography: Inter or system UI; mono/tabular-nums for **all** numeric columns, right-aligned.
- **Color is never the only signal:** ▲/▼ or +/− signs, text risk labels, tooltips on freshness dots.
- One formatting utility: adaptive price precision (BTC 2 dp, sub-cent tokens up to 8 dp), compact large values (`$1.2B`), signed percents, locale time with UTC on hover, relative times.
- Motion: row flash on SSE updates ≤ 300 ms, disabled under `prefers-reduced-motion`.
- Responsive: desktop-first; tablet collapses sidebar to icons; mobile uses bottom nav and card lists for Scanner/Portfolio.

**7.4 App shell**
- Single left sidebar (no duplicates): Overview, Scanner, Assets, Portfolio, Backtests, Memes, Sectors, Alerts, Research, System, Settings.
- Top bar: command palette trigger (Ctrl/Cmd+K), data-mode pill, exchange, regime badge with confidence, SSE status (connected / reconnecting / offline), theme toggle, user menu.
- Bottom status bar: last scan age, ingestion lag, "Paper trading only".
- Global error boundary, per-route `error.tsx`, per-widget ErrorState with retry; skeletons matching final layout (no layout shift).

**7.5 Pages**
- **Scanner (build first):** virtualized table with Symbol (+name, sector), price, 1D/7D/30D, opportunity score bar, factor mini-scores, risk-flag chips, freshness dot + age, 7-day sparkline. Server-side sort/filter/pagination via URL params. Filters: asset class, sector, min score (default **0**), exclude risk flags, hide stale, search. Column visibility, pinned Symbol, CSV export. **Row click opens a right-side drawer** with the explainability waterfall (factor contributions and penalties → final score), raw features, "partial data" badge, link to the asset page. Live SSE diffs with cell flash and a pause control. States: loading, empty (guided onboarding with an API-triggered action if permitted, never a shell command), error, stale banner.
- **Overview:** regime card (+confidence, rationale), breadth, BTC/ETH price with 1D % (omit deltas if the comparison period lacks data), top opportunities, mini sector heatmap, latest alerts.
- **Asset `/assets/[symbol]`:** header (price, 24h change, freshness, flags); candlestick chart with timeframe switcher, volume pane, EMA20/50/200 toggle, regime shading, score-crossing and paper-trade markers; factor radar, score history, feature table with tooltips/glossary, explainability waterfall, relative strength vs BTC/ETH/sector; actions: watchlist, order ticket.
- **Paper Portfolio:** summary (equity, cash, exposure, day P&L, drawdown gauge vs circuit-breaker), positions (live mark-to-market, weight, stop/TP), open orders, fills, equity curve. **Order ticket:** symbol, side, type, quantity or USD, optional SL/TP, auto `idempotency_key`; **preview step** (estimated fill, spread + slippage + fee breakdown, resulting weight, **risk-check list** with plain-language pass/fail reasons); confirm step; submit disabled on stale price with explanation; rejection codes translated to messages. Account reset needs typed confirmation. Read-only ledger view with reconciliation badge.
- **Backtest Lab:** Zod-validated form (strategy, universe, date range, capital, fees, slippage, limits, parameters) with an assumptions summary; **never auto-run on load**; job progress with stage text and cancel; runs list. Results: metrics grid with confidence intervals, equity vs benchmark, underwater drawdown, monthly-returns heatmap, cost-stress table, regime breakdown, sortable trade table (click a trade → entry/exit on the chart; `low_confidence` trades flagged), reproducibility header (code version, config hash, data hash, range, universe), HTML/PDF export. Compare 2–4 runs. Parameter-sweep heatmap with in-sample/out-of-sample labels.
- **Meme Radar:** strong risk framing; table with chain/DEX, adaptive-precision price, liquidity, volume, buy pressure, top-10 holder %, pair age, score, risk level, flags (render separators with components or text, never HTML entities in data cells); detail drawer with factor bars, gross → penalties → net score, penalty reasons, radar, pool address with copy and explorer link.
- **Sectors:** rotation chart, sector table (1D/7D/30D, breadth, status), drill-down.
- **Alerts:** inbox, rule builder (score threshold, regime change, stale feed, risk flag), channels (in-app, Telegram, Discord, email), cooldowns, quiet hours, test-send.
- **Research:** IC (Pearson + Spearman) over time, hit rate, mean forward return by score decile for 1d/7d/30d with sample sizes, CIs and small-sample warnings, plain-language explainer.
- **System:** per-exchange ingestion lag, stale assets, worker heartbeat, scan duration, API latency, ledger reconciliation status, recent errors, versions, data mode.
- **Settings:** theme, number format/timezone, default filters, notification preferences, watchlists, API keys (if multi-user).

**7.6 Data fetching and streaming**
- All calls through the generated client; no hand-written backend fetch in components.
- TanStack Query with per-resource `staleTime`; retry with backoff on network errors only.
- `useEventStream(url)`: auto-reconnect with exponential backoff + jitter, `Last-Event-ID` resume, status exposed to the status bar, pause/resume, pauses when the tab is hidden, applies diffs to the query cache.
- Optimistic updates only for harmless UI state (watchlists), never for orders. Mutations send CSRF token and `Idempotency-Key`.

**7.7 Streamlit bugs not to reproduce (present in `apps/dashboard/app.py`)**
- Sidebar header and nav radio rendered twice with different labels (🏛️ vs 🏦), so a page can fail to route.
- Hardcoded BTC 64000 / ETH 3400 fallbacks and fake "+5.2% vs 7D" deltas.
- `&bull;` inside `st.dataframe` and `<span>` inside backticks don't render.
- Selectbox fallback `["BTC"]` then `.iloc[0]` crashes when BTC isn't in the data.
- `init_db()`/`seed_default_universe()` on every rerun; N+1 queries; a new thread and event loop per call.
- Notebooks use an outdated API (`BacktestConfig(symbols=..., commission_rate=...)`, `engine.run(session)`).

**7.8 Quality bars**
- Performance: 500-row scanner scrolls at 60 fps; scanner route initial JS ≤ 250 KB gzipped (lazy-load charts); LCP < 2.5 s; no layout shift.
- Accessibility: WCAG 2.2 AA; full keyboard operation (tables, drawers, palette); visible focus; chart data-table alternatives; axe with zero serious violations in Playwright.
- Testing: unit tests for formatters/hooks; component tests for DataTable, OrderTicket (validation + preview), FreshnessDot, ExplainPanel; Playwright e2e (login → scanner filter → drawer → asset → preview + submit paper order → portfolio updates → run backtest → results); visual snapshots in dark and light.
- Security: CSP headers, httpOnly + SameSite cookies, validation on every form, no `dangerouslySetInnerHTML` with data-derived content.
- Resilience: every widget has loading/empty/error/stale states; offline banner when SSE is down > 30 s.

**7.9 UI build order** (stop and report after each step)
1. Scaffold `apps/web`, tokens, theme, formatters, generated client, auth, shell, CI (tsc, ESLint incl. fallback rule, Vitest, Playwright smoke).
2. Shared components (DataTable, ScoreBadge, FreshnessDot, DeltaCell, Sparkline, EmptyState, ErrorState, Skeletons).
3. Scanner with drawer + SSE.
4. Overview.
5. Asset deep-dive.
6. Portfolio + order ticket.
7. Backtest Lab.
8. Research + System.
9. Memes, Sectors, Alerts, Settings.

**UI Phase Report additions:** screenshots (desktop dark, desktop light, mobile), Lighthouse scores, axe results, test counts.

### PHASE 8 — Product features (API + UI + tests for each, in this order)
1. Alert delivery to Telegram/Discord/email via the existing dispatchers, with cooldowns, quiet hours, in-app inbox.
2. Watchlists, tags, and trade-journal notes on paper trades.
3. Asset compare view and portfolio analytics (correlation heatmap, sector exposure, risk contribution, stress scenario such as "BTC −20%").
4. Strategy comparison and parameter-sweep heatmap with a true in-sample/out-of-sample split.
5. Reproducible report export (HTML/PDF): code version, config, data hash, assumptions, cost-stress table.
6. Later, only if I ask: websocket (CCXT Pro) ingestion, funding/basis strategies, short and market-neutral support.

### PHASE 9 — Ship
- Retire `apps/dashboard` and `docker/Dockerfile.dashboard`; add the web container to compose behind the reverse proxy.
- Update README, ARCHITECTURE_SPEC and runbooks to v3.0; regenerate notebooks from the real API and add a CI job that executes them.
- Tag `v3.0.0` with a changelog (Fixed / Added / Changed / Security).

---

## 6. TESTING POLICY (all phases)
- Property-based tests (Hypothesis) for the execution simulator and metrics (fills never better than the base price, drawdown never positive, etc.).
- Contract tests against recorded exchange responses; load test of the scanner with 200+ assets; ledger reconciliation tests; notebook-execution test in CI; OpenAPI diff check; coverage ratchet.

## 7. DEFINITION OF DONE (every phase)
- [ ] Failing test written first for each bug; now passing.
- [ ] Full suite, ruff, mypy (and for UI: ESLint, `tsc`, Vitest, Playwright) green; coverage not below baseline.
- [ ] No new hardcoded prices, defaults masquerading as data, or secrets (UI fallback lint passes).
- [ ] Migrations have upgrade and downgrade, tested on SQLite and Postgres.
- [ ] Docs updated (README, spec, runbooks as relevant).
- [ ] For UI pages: loading/empty/error/stale states, keyboard and screen-reader pass, responsive at 375/768/1280/1920 px.
- [ ] All eight invariants confirmed explicitly.
- [ ] Phase Report delivered.

## 8. PHASE REPORT FORMAT
```
Phase N — <name>
Summary: 3–5 sentences.
Changes: files/modules touched and why.
Tests: added/changed, before vs after pass counts.
Metrics: performance numbers (e.g., backtest runtime before/after, Lighthouse).
Decisions & trade-offs: what you chose and what you rejected.
Risks / follow-ups: anything unfinished or needing my input.
Invariants check: confirm each of the 8 invariants.
Questions: numbered, only if blocking.
```

## 9. OUT OF SCOPE (unless I ask)
Live trading or real order routing, custody or wallet features, profitability claims, new paid data vendors, rewriting the scoring philosophy, changing the license, social/sharing features beyond read-only report links, native mobile apps, and any visual flourish that hides data-quality information.

## 10. START NOW
1. Run section 4 (First Actions) and send me the baseline.
2. Do Phase 0, then Phase 1, then stop and send the Phase Report.
3. Before Phase 7 begins, read `apps/dashboard/app.py`, `apps/dashboard/components/*` and `apps/api/routes/*`, list which endpoints exist and which are missing for the Scanner page, and wait for my go-ahead.
</USER_REQUEST>
<ADDITIONAL_METADATA>
The current local time is: 2026-10-02T14:21:15+05:30.

The user's current state is as follows:
Active Document: m:\CRYPTO-\src\ingestion\live_ingestor.py (LANGUAGE_PYTHON)
Cursor is on line: 1
Other open documents:
- m:\CRYPTO-\src\features\market_regime.py (LANGUAGE_PYTHON)
- m:\CRYPTO-\src\features\liquidity.py (LANGUAGE_PYTHON)
- m:\CRYPTO-\tests\unit\test_providers.py (LANGUAGE_PYTHON)
- m:\CRYPTO-\apps\api\routes\assets.py (LANGUAGE_PYTHON)
- m:\CRYPTO-\tests\conftest.py (LANGUAGE_PYTHON)
</ADDITIONAL_METADATA>