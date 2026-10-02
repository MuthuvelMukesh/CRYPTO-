# Crypto Intelligence Platform — v3.0 Baseline Report

**Recorded**: 2026-10-02 (Local Time: 14:28 IST)  
**Environment**: Windows, Python 3.13.9, SQLite / in-memory cache fallback

---

## 1. Installation Baseline (`pip install -e ".[dev]"`)

- **Command**: `pip install -e ".[dev]"`
- **Result**: `Successfully installed crypto-intelligence-0.1.0 streamlit-1.56.0 tenacity-9.1.4 tornado-6.5.10`
- **Dependencies**:
  - `setuptools` build backend
  - Core quantitative stack: `ccxt`, `polars`, `numpy`, `pandas`, `structlog`, `pydantic`, `fastapi`, `sqlalchemy`
  - Dev dependencies: `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`

---

## 2. Test Suite Baseline (`pytest -q`)

- **Command**: `pytest -q`
- **Total Tests Collected**: 103
- **Passed**: 103
- **Failed**: 0
- **Errors**: 0
- **Warnings**: 1 (`PendingDeprecationWarning: Please use import python_multipart instead.` from Starlette formparsers)
- **Runtime**: ~30.34s
- **Breakdown**:
  - `tests/regression/test_v2_synthetic_fallback_regression.py`: 13 passed
  - `tests/bias/`: 3 passed (lookahead bias, backtest bias, survivorship bias)
  - `tests/integration/`: 10 passed (health, paper pipeline, meme radar, backtest pipeline, feature pipeline, alerts)
  - `tests/unit/`: 77 passed (scoring, features, backtest execution/metrics/strategies, ML models, OHLCV validator, broker, risk, providers, utils)

---

## 3. Linter Baseline (`ruff check .`)

- **Command**: `ruff check .`
- **Total Violations**: 30 errors across codebase
- **Categories**:
  - `F401`: Unused imports (e.g. `datetime` in `src/ingestion/universe.py`, `ListingStatus`, `Timeframe`, `utc_now`)
  - `I001`: Unsorted/unformatted import blocks (`tests/regression/`, `src/scanner/pipeline.py`, etc.)
  - `F841`: Local variable assigned but never used (`inserted_objects` in regression test)
- **Auto-fixable**: 23 errors fixable with `ruff check . --fix`

---

## 4. Type Checker Baseline (`mypy src apps`)

- **Command**: `mypy src apps`
- **Checked Files**: 95 source files
- **Total Errors**: 36 errors across 17 files
- **Primary Issues**:
  - Missing stubs / untyped imports: `pandas` (`import-untyped`), `plotly.graph_objects`, `sklearn.*`
  - Typo / naming mismatches:
    - `src/features/volatility.py:71`: `ndarray` passed where `Sequence[float]` expected
    - `src/backtesting/strategies/__init__.py:23`: missing `name` argument in `BaseStrategy`
    - `src/scoring/engine.py:113-114`: type annotation mismatch on score dict
    - `src/ingestion/providers/dexscreener_provider.py`: duplicate `close` method definition
    - `src/ingestion/providers/ccxt_provider.py`: unexpected keyword argument `details` for `ExternalProviderUnavailableError`
    - `src/backtesting/engine.py`: dict vs optional dict assignments
    - `apps/api/routes/health.py`: undefined variable `age` in error fallback branch
    - `apps/api/routes/scanner.py`: operand `>=` with `int` and `None`
    - Enum mismatch: `src.config.settings.DataMode` vs `src.config.constants.DataMode`

---

## 5. Configuration & Environment Encoding

- `.env.example` re-encoded as clean UTF-8 without BOM.
- `DATA_MODE=LIVE` default configured.
- `LIVE_TRADING_ENABLED=false` enforced by settings validator and runtime architecture.
