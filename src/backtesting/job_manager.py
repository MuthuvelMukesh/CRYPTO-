"""Asynchronous Backtest Job Management & Execution Engine — Platform v3.0.

Provides:
- Non-blocking async backtest job dispatch
- Real-time progress tracking (0.0 -> 1.0)
- Execution cancellation
- Parameter capping (max 50 symbols, max 5 years date range)
- Deterministic hashing of code version, configuration, and simulation dataset
"""

import asyncio
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import select

from src.backtesting.engine import BacktestEngine
from src.backtesting.models import BacktestConfig, BacktestResult, SlippageModelType
from src.backtesting.strategies import get_strategy
from src.config.settings import get_settings
from src.database.models import OHLCV, Asset, Backtest, BacktestTrade
from src.database.session import get_session_factory
from src.utils.logging import get_logger

logger = get_logger("src.backtesting.job_manager")


class BacktestJob:
    """In-flight or completed asynchronous backtest execution record."""

    def __init__(
        self,
        job_id: str,
        config: BacktestConfig,
        symbols: list[str],
        code_version: str,
        config_hash: str,
    ) -> None:
        self.job_id = job_id
        self.config = config
        self.symbols = symbols
        self.code_version = code_version
        self.config_hash = config_hash
        self.data_hash: str | None = None

        self.status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"] = "PENDING"
        self.progress: float = 0.0
        self.error_message: str | None = None
        self.created_at: datetime = datetime.now(UTC)
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None

        self.result: BacktestResult | None = None
        self._task: asyncio.Task | None = None

    def to_summary(self) -> dict[str, Any]:
        """Serialize job state for client status polling."""
        res_summary = None
        if self.result is not None:
            res_summary = {
                "total_return_pct": self.result.metrics.total_return_pct,
                "cagr": self.result.metrics.cagr,
                "sharpe_ratio": self.result.metrics.sharpe_ratio,
                "sortino_ratio": self.result.metrics.sortino_ratio,
                "max_drawdown_pct": self.result.metrics.max_drawdown_pct,
                "win_rate": self.result.metrics.win_rate,
                "profit_factor": self.result.metrics.profit_factor,
                "benchmark_return_pct": self.result.metrics.benchmark_return_pct,
                "deflated_sharpe_ratio": self.result.deflated_sharpe_ratio,
                "survivorship_bias_status": self.result.survivorship_bias_status,
                "total_trades": len(self.result.trades),
            }

        return {
            "job_id": self.job_id,
            "status": self.status,
            "progress": round(self.progress, 3),
            "strategy_name": self.config.strategy_name,
            "strategy_version": self.config.strategy_version,
            "symbols": self.symbols,
            "code_version": self.code_version,
            "config_hash": self.config_hash,
            "data_hash": self.data_hash,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "summary": res_summary,
        }


class BacktestJobManager:
    """Manages asynchronous backtest job lifecycles and background execution."""

    MAX_SYMBOLS: int = 50
    MAX_DATE_RANGE_DAYS: int = 1825  # 5 years

    def __init__(self) -> None:
        self._jobs: dict[str, BacktestJob] = {}

    def validate_and_cap_parameters(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
    ) -> tuple[list[str], datetime, datetime]:
        """Enforce architectural safety limits on backtest parameters."""
        if start_date >= end_date:
            raise ValueError(f"start_date ({start_date}) must be strictly before end_date ({end_date}).")

        # Cap symbols
        if len(symbols) > self.MAX_SYMBOLS:
            logger.warning("capping_symbols_list", original=len(symbols), cap=self.MAX_SYMBOLS)
            symbols = symbols[: self.MAX_SYMBOLS]

        # Cap date range
        delta = end_date - start_date
        if delta > timedelta(days=self.MAX_DATE_RANGE_DAYS):
            capped_start = end_date - timedelta(days=self.MAX_DATE_RANGE_DAYS)
            logger.warning(
                "capping_date_range",
                original_days=delta.days,
                max_days=self.MAX_DATE_RANGE_DAYS,
                new_start=capped_start,
            )
            start_date = capped_start

        return symbols, start_date, end_date

    def compute_config_hash(self, config_dict: dict[str, Any]) -> str:
        """Calculate deterministic SHA-256 hash of simulation configuration."""
        canonical_json = json.dumps(config_dict, sort_keys=True, default=str)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()[:16]

    def compute_data_hash(self, candle_dict: dict[str, list[dict]]) -> str:
        """Calculate deterministic SHA-256 hash of input candle series."""
        hasher = hashlib.sha256()
        for sym in sorted(candle_dict.keys()):
            for c in candle_dict[sym]:
                hasher.update(f"{sym}:{c.get('time')}:{c.get('close')}".encode())
        return hasher.hexdigest()[:16]

    def create_job(
        self,
        strategy_name: str,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        initial_capital: float = 100000.0,
        maker_fee_bps: float = 2.0,
        taker_fee_bps: float = 5.0,
        slippage_model: SlippageModelType = SlippageModelType.MARKET_IMPACT,
        fixed_slippage_bps: float = 5.0,
        impact_gamma: float = 0.1,
        benchmark_symbol: str = "BTC",
        max_open_positions: int = 10,
        max_position_weight: float = 0.25,
        cash_buffer_pct: float = 0.02,
        point_in_time_universe: bool = True,
        parameters: dict[str, Any] | None = None,
    ) -> BacktestJob:
        """Instantiate and register an asynchronous backtest job."""
        settings = get_settings()
        symbols, start_date, end_date = self.validate_and_cap_parameters(symbols, start_date, end_date)

        strategy = get_strategy(strategy_name, parameters=parameters or {})
        config = BacktestConfig(
            strategy_name=strategy_name,
            strategy_version=strategy.version,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            maker_fee_bps=maker_fee_bps,
            taker_fee_bps=taker_fee_bps,
            slippage_model=slippage_model,
            fixed_slippage_bps=fixed_slippage_bps,
            impact_gamma=impact_gamma,
            benchmark_symbol=benchmark_symbol,
            max_open_positions=max_open_positions,
            max_position_weight=max_position_weight,
            cash_buffer_pct=cash_buffer_pct,
            point_in_time_universe=point_in_time_universe,
            parameters=parameters or {},
        )

        job_id = str(uuid.uuid4())
        config_hash = self.compute_config_hash(config.__dict__)
        job = BacktestJob(
            job_id=job_id,
            config=config,
            symbols=symbols,
            code_version=settings.APP_VERSION,
            config_hash=config_hash,
        )

        self._jobs[job_id] = job

        # Launch background execution task
        job._task = asyncio.create_task(self._run_job_async(job, strategy))
        return job

    def get_job(self, job_id: str) -> BacktestJob | None:
        """Lookup job by ID."""
        return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running or pending backtest task."""
        job = self.get_job(job_id)
        if not job or job.status in ("COMPLETED", "FAILED", "CANCELLED"):
            return False

        if job._task and not job._task.done():
            job._task.cancel()
        job.status = "CANCELLED"
        job.completed_at = datetime.now(UTC)
        logger.info("backtest_job_cancelled", job_id=job_id)
        return True

    async def _run_job_async(self, job: BacktestJob, strategy) -> None:
        """Internal asynchronous runner for executing and persisting backtests."""
        try:
            job.status = "RUNNING"
            job.started_at = datetime.now(UTC)
            job.progress = 0.1

            # Fetch candle data
            factory = get_session_factory()
            historical_candles: dict[str, list[dict[str, Any]]] = {}
            historical_features: dict[str, list[dict[str, Any]]] = {}
            delisted_dates: dict[str, datetime] = {}

            all_symbols = list(set([job.config.benchmark_symbol] + job.symbols))

            async with factory() as session:
                for idx, sym in enumerate(all_symbols):
                    # Update progress
                    job.progress = 0.1 + (0.3 * (idx / max(1, len(all_symbols))))
                    asset_res = await session.execute(select(Asset).where(Asset.symbol == sym))
                    asset_obj = asset_res.scalars().first()
                    if asset_obj and asset_obj.delisted_at:
                        delisted_dates[sym] = asset_obj.delisted_at

                    # Query OHLCV
                    candle_stmt = (
                        select(OHLCV)
                        .where(
                            OHLCV.market_id.like(f"%{sym}%"),
                            OHLCV.time >= job.config.start_date,
                            OHLCV.time <= job.config.end_date,
                        )
                        .order_by(OHLCV.time)
                    )
                    c_res = await session.execute(candle_stmt)
                    candles = c_res.scalars().all()
                    if candles:
                        historical_candles[sym] = [
                            {
                                "time": c.time if c.time.tzinfo else c.time.replace(tzinfo=UTC),
                                "open": float(c.open),
                                "high": float(c.high),
                                "low": float(c.low),
                                "close": float(c.close),
                                "volume": float(c.volume),
                                "volume_usd": float(getattr(c, "quote_volume", 0.0) or c.volume * c.close),
                            }
                            for c in candles
                        ]

            job.data_hash = self.compute_data_hash(historical_candles)
            job.progress = 0.5

            # If historical candles are empty, construct a synthetic baseline for testing if in SYNTHETIC_TEST mode
            settings = get_settings()
            if not historical_candles:
                if settings.DATA_MODE == "SYNTHETIC_TEST":
                    t0 = job.config.start_date
                    for sym in all_symbols:
                        historical_candles[sym] = [
                            {
                                "time": t0 + timedelta(days=i),
                                "open": 100.0 + i,
                                "high": 105.0 + i,
                                "low": 95.0 + i,
                                "close": 102.0 + i,
                                "volume": 1000.0,
                                "volume_usd": 100000.0,
                            }
                            for i in range(30)
                        ]
                else:
                    raise RuntimeError("No historical candle records found in database for requested symbols and date range.")

            job.progress = 0.7

            # Execute simulation
            engine = BacktestEngine(config=job.config, strategy=strategy)
            result = engine.run(
                historical_candles=historical_candles,
                historical_features=historical_features,
                delisted_dates=delisted_dates,
            )

            job.progress = 0.9
            job.result = result

            # Persist to database
            async with factory() as session:
                record = Backtest(
                    id=job.job_id,
                    strategy_name=job.config.strategy_name,
                    strategy_version=job.config.strategy_version,
                    start_time=job.config.start_date,
                    end_time=job.config.end_date,
                    initial_capital=job.config.initial_capital,
                    parameters=job.config.parameters,
                    total_return_pct=result.metrics.total_return_pct,
                    cagr=result.metrics.cagr,
                    sharpe_ratio=result.metrics.sharpe_ratio,
                    sortino_ratio=result.metrics.sortino_ratio,
                    max_drawdown_pct=result.metrics.max_drawdown_pct,
                    win_rate=result.metrics.win_rate,
                    profit_factor=result.metrics.profit_factor,
                    benchmark_return_pct=result.metrics.benchmark_return_pct,
                    created_at=datetime.now(UTC),
                )
                session.add(record)

                for t in result.trades:
                    trade_record = BacktestTrade(
                        id=t.trade_id,
                        backtest_id=job.job_id,
                        asset_id=t.asset_id,
                        entry_time=t.entry_time,
                        exit_time=t.exit_time,
                        entry_price=t.entry_price,
                        exit_price=t.exit_price,
                        position_size=t.position_size,
                        pnl_usd=t.pnl_usd,
                        pnl_pct=t.pnl_pct,
                        fees_usd=t.fees_usd,
                        slippage_usd=t.slippage_usd,
                        exit_reason=t.exit_reason.value if hasattr(t.exit_reason, "value") else str(t.exit_reason),
                    )
                    session.add(trade_record)

                await session.commit()

            job.progress = 1.0
            job.status = "COMPLETED"
            job.completed_at = datetime.now(UTC)
            logger.info("backtest_job_completed_successfully", job_id=job.job_id)

        except asyncio.CancelledError:
            job.status = "CANCELLED"
            job.completed_at = datetime.now(UTC)
            logger.info("backtest_job_task_cancelled", job_id=job.job_id)
        except Exception as exc:
            job.status = "FAILED"
            job.error_message = str(exc)
            job.completed_at = datetime.now(UTC)
            logger.error("backtest_job_failed", job_id=job.job_id, error=str(exc))


_global_job_manager: BacktestJobManager | None = None


def get_job_manager() -> BacktestJobManager:
    """Return the global BacktestJobManager singleton."""
    global _global_job_manager
    if _global_job_manager is None:
        _global_job_manager = BacktestJobManager()
    return _global_job_manager
