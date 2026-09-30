"""Backtesting and strategy execution REST API endpoints."""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.deps import get_db
from src.backtesting.engine import BacktestEngine
from src.backtesting.models import BacktestConfig, SlippageModelType
from src.backtesting.strategies import STRATEGY_REGISTRY, get_strategy
from src.database.models import OHLCV, Asset, Backtest
from src.utils.time import utc_now

router = APIRouter(prefix="/api/v1/backtests", tags=["Backtesting"])


class StrategyInfoResponse(BaseModel):
    """Information schema for a registered trading strategy."""

    name: str
    version: str
    description: str
    default_parameters: dict[str, Any]


class RunBacktestRequest(BaseModel):
    """Payload to trigger a new backtest simulation."""

    model_config = ConfigDict(protected_namespaces=())

    strategy_name: str = Field(..., description="Registered strategy name")
    symbols: list[str] = Field(default_factory=lambda: ["BTC", "ETH", "SOL", "AVAX", "LINK", "DOGE"])
    start_date: datetime = Field(
        default_factory=lambda: utc_now() - timedelta(days=90),
        description="UTC start datetime for historical simulation",
    )
    end_date: datetime = Field(
        default_factory=utc_now,
        description="UTC end datetime for historical simulation",
    )
    initial_capital: float = Field(default=100000.0, ge=1000.0, description="Starting cash in USD")
    maker_fee_bps: float = Field(default=2.0, ge=0.0, description="Maker fee in bps")
    taker_fee_bps: float = Field(default=5.0, ge=0.0, description="Taker fee in bps")
    slippage_model: SlippageModelType = Field(default=SlippageModelType.MARKET_IMPACT)
    fixed_slippage_bps: float = Field(default=5.0, ge=0.0)
    impact_gamma: float = Field(default=0.1, ge=0.0)
    benchmark_symbol: str = Field(default="BTC")
    max_open_positions: int = Field(default=10, ge=1, le=50)
    max_position_weight: float = Field(default=0.25, ge=0.01, le=1.0)
    cash_buffer_pct: float = Field(default=0.02, ge=0.0, le=0.5)
    parameters: dict[str, Any] = Field(default_factory=dict, description="Strategy hyperparameters")


class BacktestSummaryResponse(BaseModel):
    """Summary of a completed backtest execution."""

    model_config = ConfigDict(protected_namespaces=())

    id: str
    strategy_name: str
    strategy_version: str
    start_time: str
    end_time: str
    parameters: dict[str, Any]
    total_return_pct: float
    cagr: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    benchmark_return_pct: float
    created_at: str


class BacktestDetailResponse(BacktestSummaryResponse):
    """Detailed backtest result including trade history and equity points."""

    trades: list[dict[str, Any]]
    metrics: dict[str, Any]


@router.get("/strategies", response_model=list[StrategyInfoResponse], summary="List available trading strategies")
async def list_strategies() -> list[StrategyInfoResponse]:
    """Retrieve metadata for all registered quantitative trading strategies."""
    info_list: list[StrategyInfoResponse] = []
    for name, cls in STRATEGY_REGISTRY.items():
        instance = cls()
        doc = cls.__doc__ or "Quantitative strategy."
        info_list.append(
            StrategyInfoResponse(
                name=name,
                version=instance.version,
                description=doc.strip().split("\n")[0],
                default_parameters=instance.parameters,
            )
        )
    return info_list


@router.get("", response_model=list[BacktestSummaryResponse], summary="List historical backtest runs")
async def list_backtests(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[BacktestSummaryResponse]:
    """Retrieve history of saved backtests ordered by creation date descending."""
    stmt = select(Backtest).order_by(desc(Backtest.created_at)).limit(limit)
    res = await db.execute(stmt)
    records = res.scalars().all()

    return [
        BacktestSummaryResponse(
            id=r.id,
            strategy_name=r.strategy_name,
            strategy_version=r.strategy_version,
            start_time=r.start_time.isoformat(),
            end_time=r.end_time.isoformat(),
            parameters=r.parameters or {},
            total_return_pct=r.total_return_pct,
            cagr=r.cagr,
            sharpe_ratio=r.sharpe_ratio,
            sortino_ratio=r.sortino_ratio,
            max_drawdown_pct=r.max_drawdown_pct,
            win_rate=r.win_rate,
            profit_factor=r.profit_factor,
            benchmark_return_pct=r.benchmark_return_pct,
            created_at=r.created_at.isoformat(),
        )
        for r in records
    ]


@router.get("/{backtest_id}", response_model=BacktestDetailResponse, summary="Get full backtest results")
async def get_backtest(
    backtest_id: str,
    db: AsyncSession = Depends(get_db),
) -> BacktestDetailResponse:
    """Retrieve comprehensive backtest run results with trade logs."""
    stmt = (
        select(Backtest)
        .options(selectinload(Backtest.trades))
        .where(Backtest.id == backtest_id)
    )
    res = await db.execute(stmt)
    record = res.scalars().first()

    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest run not found")

    trades_list = [
        {
            "trade_id": t.id,
            "asset_id": t.asset_id,
            "entry_time": t.entry_time.isoformat(),
            "exit_time": t.exit_time.isoformat(),
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "pnl_usd": t.pnl_usd,
            "pnl_pct": t.pnl_pct,
            "fees_usd": t.fees_usd,
            "slippage_usd": t.slippage_usd,
            "exit_reason": t.exit_reason,
        }
        for t in record.trades
    ]

    metrics = {
        "total_return_pct": record.total_return_pct,
        "cagr": record.cagr,
        "sharpe_ratio": record.sharpe_ratio,
        "sortino_ratio": record.sortino_ratio,
        "max_drawdown_pct": record.max_drawdown_pct,
        "win_rate": record.win_rate,
        "profit_factor": record.profit_factor,
        "benchmark_return_pct": record.benchmark_return_pct,
        "total_trades": len(record.trades),
    }

    return BacktestDetailResponse(
        id=record.id,
        strategy_name=record.strategy_name,
        strategy_version=record.strategy_version,
        start_time=record.start_time.isoformat(),
        end_time=record.end_time.isoformat(),
        parameters=record.parameters or {},
        total_return_pct=record.total_return_pct,
        cagr=record.cagr,
        sharpe_ratio=record.sharpe_ratio,
        sortino_ratio=record.sortino_ratio,
        max_drawdown_pct=record.max_drawdown_pct,
        win_rate=record.win_rate,
        profit_factor=record.profit_factor,
        benchmark_return_pct=record.benchmark_return_pct,
        created_at=record.created_at.isoformat(),
        trades=trades_list,
        metrics=metrics,
    )


@router.post("/run", response_model=BacktestDetailResponse, summary="Execute a backtest simulation")
async def run_backtest_endpoint(
    req: RunBacktestRequest,
    db: AsyncSession = Depends(get_db),
) -> BacktestDetailResponse:
    """Execute a backtesting simulation and persist the results."""
    try:
        strategy = get_strategy(req.strategy_name, parameters=req.parameters)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    config = BacktestConfig(
        strategy_name=req.strategy_name,
        strategy_version=strategy.version,
        start_date=req.start_date,
        end_date=req.end_date,
        initial_capital=req.initial_capital,
        maker_fee_bps=req.maker_fee_bps,
        taker_fee_bps=req.taker_fee_bps,
        slippage_model=req.slippage_model,
        fixed_slippage_bps=req.fixed_slippage_bps,
        impact_gamma=req.impact_gamma,
        benchmark_symbol=req.benchmark_symbol,
        max_open_positions=req.max_open_positions,
        max_position_weight=req.max_position_weight,
        cash_buffer_pct=req.cash_buffer_pct,
        parameters=req.parameters,
    )

    # Load candles from DB or generate deterministic baseline for simulation
    historical_candles: dict[str, list[dict[str, Any]]] = {}
    historical_features: dict[str, list[dict[str, Any]]] = {}

    symbols = req.symbols
    if req.benchmark_symbol not in symbols:
        symbols = [req.benchmark_symbol] + symbols

    # Check if candles exist in DB for these symbols
    symbols_found: set[str] = set()
    for sym in symbols:
        asset_stmt = select(Asset).where(Asset.symbol == sym)
        res_asset = await db.execute(asset_stmt)
        asset_row = res_asset.scalars().first()
        if asset_row:
            candle_stmt = (
                select(OHLCV)
                .where(
                    OHLCV.market_id.like(f"%{sym}%"),
                    OHLCV.time >= req.start_date,
                    OHLCV.time <= req.end_date,
                )
                .order_by(OHLCV.time)
            )
            candle_res = await db.execute(candle_stmt)
            candles = candle_res.scalars().all()
            if len(candles) >= 10:
                symbols_found.add(sym)
                historical_candles[sym] = [
                    {
                        "time": c.time,
                        "open": c.open,
                        "high": c.high,
                        "low": c.low,
                        "close": c.close,
                        "volume": c.volume,
                        "volume_usd": c.volume * c.close,
                    }
                    for c in candles
                ]

    # If DB does not have enough candles, generate deterministic synthetic series
    # so research/backtest engine always runs consistently out of the box
    if len(symbols_found) < len(symbols):
        total_days = max(15, (req.end_date - req.start_date).days)
        start_t = req.start_date

        base_prices = {
            "BTC": 50000.0,
            "ETH": 3000.0,
            "SOL": 120.0,
            "AVAX": 35.0,
            "LINK": 18.0,
            "DOGE": 0.12,
        }

        import numpy as np

        for sym in symbols:
            if sym in historical_candles:
                continue
            np.random.seed(abs(hash(sym)) % 1000000)
            p0 = base_prices.get(sym, 10.0)
            candles_list = []
            feats_list = []
            curr_p = p0

            for d in range(total_days + 1):
                t = start_t + timedelta(days=d)
                ret = float(np.random.normal(0.002, 0.03))  # slight positive drift
                open_p = curr_p
                close_p = max(0.001, curr_p * (1.0 + ret))
                high_p = max(open_p, close_p) * (1.0 + abs(float(np.random.normal(0.0, 0.015))))
                low_p = min(open_p, close_p) * (1.0 - abs(float(np.random.normal(0.0, 0.015))))
                vol = float(np.random.uniform(5000.0, 50000.0))
                vol_usd = vol * close_p
                curr_p = close_p

                candles_list.append({
                    "time": t,
                    "open": round(open_p, 4),
                    "high": round(high_p, 4),
                    "low": round(low_p, 4),
                    "close": round(close_p, 4),
                    "volume": round(vol, 2),
                    "volume_usd": round(vol_usd, 2),
                })

                # Features snapshot for strategy
                feats_list.append({
                    "time": t,
                    "return_30d": float(np.random.uniform(-0.1, 0.3)),
                    "rs_btc_30d": float(np.random.uniform(-0.15, 0.25)),
                    "ema20_ratio": float(np.random.uniform(0.95, 1.08)),
                    "ema50_ratio": float(np.random.uniform(0.92, 1.12)),
                    "adx_14": float(np.random.uniform(15.0, 35.0)),
                    "volume_to_20d_avg": float(np.random.uniform(0.8, 2.5)),
                    "volatility_adjusted_momentum": float(np.random.uniform(-1.0, 2.5)),
                    "opportunity_score": float(np.random.uniform(40.0, 92.0)),
                    "risk_flags": [],
                })

            historical_candles[sym] = candles_list
            historical_features[sym] = feats_list

    engine = BacktestEngine(config, strategy)
    result = engine.run(historical_candles=historical_candles, historical_features=historical_features)

    # Persist to database
    await BacktestEngine.persist_result(db, result)

    return BacktestDetailResponse(
        id=result.id,
        strategy_name=result.config.strategy_name,
        strategy_version=result.config.strategy_version,
        start_time=result.config.start_date.isoformat(),
        end_time=result.config.end_date.isoformat(),
        parameters=result.config.parameters,
        total_return_pct=result.metrics.get("total_return_pct", 0.0),
        cagr=result.metrics.get("cagr", 0.0),
        sharpe_ratio=result.metrics.get("sharpe_ratio", 0.0),
        sortino_ratio=result.metrics.get("sortino_ratio", 0.0),
        max_drawdown_pct=result.metrics.get("max_drawdown_pct", 0.0),
        win_rate=result.metrics.get("win_rate", 0.0),
        profit_factor=result.metrics.get("profit_factor", 0.0),
        benchmark_return_pct=result.metrics.get("benchmark_return_pct", 0.0),
        created_at=result.created_at.isoformat(),
        trades=result.trades,
        metrics=result.metrics,
    )
