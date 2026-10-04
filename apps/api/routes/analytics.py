"""Portfolio analytics, cross-asset correlation, and stress testing REST API endpoints — Platform v3.0.

Provides:
- Multi-asset Pearson correlation matrix and return metrics (`GET /api/v1/analytics/correlation`)
- Portfolio macro stress scenario simulations (`GET /api/v1/analytics/portfolio-stress`)
- Sector exposure breakdown, concentration risk (HHI), and risk contribution (`GET /api/v1/analytics/sector-exposure`)
"""

import math
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import AuthIdentity, get_current_auth, get_db
from src.database.models import OHLCV, Asset
from src.paper.broker import PaperBroker

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics & Stress Testing"])
broker = PaperBroker()


class CorrelationRow(BaseModel):
    """Correlation values for a single base asset against all comparison assets."""

    symbol: str
    correlations: dict[str, float | None]


class AssetStatItem(BaseModel):
    """Statistical summary for an asset over the sample period."""

    symbol: str
    current_price: float | None
    volatility_annualized: float | None
    sample_count: int


class CorrelationResponse(BaseModel):
    """Multi-asset correlation matrix and risk statistics."""

    symbols: list[str]
    timeframe: str
    lookback_samples: int
    matrix: list[CorrelationRow]
    stats: list[AssetStatItem]
    data_mode: str = "HISTORICAL"


class PositionStressImpact(BaseModel):
    """Impact of a stress scenario on a single open position."""

    symbol: str
    side: str
    quantity: float
    current_price: float
    stressed_price: float
    current_value_usd: float
    stressed_value_usd: float
    impact_usd: float
    impact_pct: float
    risk_contribution_pct: float


class StressScenarioResult(BaseModel):
    """Outcome of a simulated stress scenario on the paper portfolio."""

    scenario_id: str
    name: str
    description: str
    base_equity_usd: float
    stressed_equity_usd: float
    pnl_impact_usd: float
    drawdown_pct: float
    position_impacts: list[PositionStressImpact]


class PortfolioStressResponse(BaseModel):
    """Comprehensive stress test simulation across macro shock scenarios."""

    model_config = ConfigDict(protected_namespaces=())

    account_id: str
    base_cash_usd: float
    base_equity_usd: float
    invested_capital_usd: float
    open_positions_count: int
    var_95_daily_usd: float | None
    var_95_daily_pct: float | None
    scenarios: list[StressScenarioResult]
    data_mode: str = "HISTORICAL"


class SectorAllocationItem(BaseModel):
    """Portfolio allocation and value for a specific market sector."""

    sector: str
    value_usd: float
    weight_pct: float
    symbols: list[str]


class AssetRiskContribution(BaseModel):
    """Marginal risk and concentration contribution of an individual holding."""

    symbol: str
    sector: str
    market_value_usd: float
    weight_pct: float
    risk_contribution_pct: float


class SectorExposureResponse(BaseModel):
    """Portfolio sector allocation, leverage, and concentration risk metrics."""

    account_id: str
    total_equity_usd: float
    cash_usd: float
    invested_usd: float
    gross_exposure_pct: float
    net_exposure_pct: float
    herfindahl_index: float
    is_concentrated: bool
    sectors: list[SectorAllocationItem]
    risk_contributions: list[AssetRiskContribution]
    data_mode: str = "HISTORICAL"


@router.get("/correlation", response_model=CorrelationResponse, summary="Compute multi-asset return correlation matrix")
async def get_correlation_matrix(
    symbols: str = Query("BTC,ETH,SOL,BNB", description="Comma-separated asset symbols"),
    timeframe: str = Query("1h", description="Candlestick timeframe (1h, 1d)"),
    limit: int = Query(100, ge=10, le=500, description="Historical sample count"),
    auth: AuthIdentity = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> CorrelationResponse:
    """Calculate Pearson correlation matrix from log-returns of monitored assets without synthetic data."""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        symbol_list = ["BTC", "ETH", "SOL", "BNB"]

    # Fetch chronological candles for each symbol
    candles_by_symbol: dict[str, dict[str, float]] = {}
    current_prices: dict[str, float | None] = {}

    for sym in symbol_list:
        market_id = f"binance:{sym}/USDT"
        stmt = (
            select(OHLCV)
            .where(OHLCV.market_id == market_id, OHLCV.timeframe == timeframe)
            .order_by(desc(OHLCV.time))
            .limit(limit)
        )
        res = await db.execute(stmt)
        candles = list(reversed(res.scalars().all()))

        if candles:
            current_prices[sym] = float(candles[-1].close)
            # Map iso time string to close price
            candles_by_symbol[sym] = {c.time.isoformat(): float(c.close) for c in candles}
        else:
            current_prices[sym] = None
            candles_by_symbol[sym] = {}

    # Calculate log returns per symbol
    returns_by_symbol: dict[str, dict[str, float]] = {}
    for sym, time_map in candles_by_symbol.items():
        sorted_times = sorted(time_map.keys())
        ret_map: dict[str, float] = {}
        for i in range(1, len(sorted_times)):
            t_prev = sorted_times[i - 1]
            t_curr = sorted_times[i]
            p_prev = time_map[t_prev]
            p_curr = time_map[t_curr]
            if p_prev > 0 and p_curr > 0:
                ret_map[t_curr] = math.log(p_curr / p_prev)
        returns_by_symbol[sym] = ret_map

    # Annualization factor for volatility
    annual_factor = math.sqrt(365 * 24) if timeframe == "1h" else math.sqrt(365)

    stats: list[AssetStatItem] = []
    for sym in symbol_list:
        rets = list(returns_by_symbol.get(sym, {}).values())
        if len(rets) >= 2:
            mean = sum(rets) / len(rets)
            variance = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
            vol = math.sqrt(variance) * annual_factor
            stats.append(
                AssetStatItem(
                    symbol=sym,
                    current_price=current_prices.get(sym),
                    volatility_annualized=round(vol, 4),
                    sample_count=len(rets),
                )
            )
        else:
            stats.append(
                AssetStatItem(
                    symbol=sym,
                    current_price=current_prices.get(sym),
                    volatility_annualized=None,
                    sample_count=len(rets),
                )
            )

    # Compute pairwise Pearson correlation
    matrix: list[CorrelationRow] = []
    for sym1 in symbol_list:
        corrs: dict[str, float | None] = {}
        r1_map = returns_by_symbol.get(sym1, {})
        for sym2 in symbol_list:
            if sym1 == sym2:
                corrs[sym2] = 1.0
                continue
            r2_map = returns_by_symbol.get(sym2, {})
            # Aligned timestamps
            common_times = set(r1_map.keys()) & set(r2_map.keys())
            if len(common_times) < 3:
                corrs[sym2] = None
                continue

            x = [r1_map[t] for t in common_times]
            y = [r2_map[t] for t in common_times]
            mean_x = sum(x) / len(x)
            mean_y = sum(y) / len(y)

            numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(len(x)))
            denom_x = sum((xi - mean_x) ** 2 for xi in x)
            denom_y = sum((yi - mean_y) ** 2 for yi in y)
            denominator = math.sqrt(denom_x * denom_y)

            if denominator > 1e-12:
                rho = max(-1.0, min(1.0, numerator / denominator))
                corrs[sym2] = round(rho, 4)
            else:
                corrs[sym2] = None

        matrix.append(CorrelationRow(symbol=sym1, correlations=corrs))

    return CorrelationResponse(
        symbols=symbol_list,
        timeframe=timeframe,
        lookback_samples=limit,
        matrix=matrix,
        stats=stats,
        data_mode="HISTORICAL",
    )


def _get_shock_percentage(symbol: str, scenario_id: str) -> float:
    """Resolve asset shock percentage for scenario without arbitrary fabrication."""
    sym = symbol.upper()
    is_meme = sym in {"DOGE", "PEPE", "SHIB", "BONK", "WIF", "FLOKI"}
    is_stable = sym in {"USDT", "USDC", "DAI", "BUSD", "FDUSD"}
    is_btc = sym == "BTC"
    is_eth_bnb = sym in {"ETH", "BNB"}

    if is_stable:
        return 0.0

    if scenario_id == "btc_minus_20":
        if is_btc:
            return -0.20
        if is_eth_bnb:
            return -0.25
        if is_meme:
            return -0.45
        return -0.35

    if scenario_id == "crypto_winter_45":
        if is_btc:
            return -0.45
        if is_eth_bnb:
            return -0.55
        if is_meme:
            return -0.80
        return -0.65

    if scenario_id == "liquidity_crisis":
        # 15% drop + 5% spread/execution slippage penalty
        return -0.20

    if scenario_id == "regulatory_alt_crackdown":
        if is_btc:
            return 0.05
        return -0.40

    if scenario_id == "bull_breakout_30":
        if is_btc:
            return 0.30
        if is_eth_bnb:
            return 0.40
        if is_meme:
            return 0.80
        return 0.60

    return -0.15


@router.get("/portfolio-stress", response_model=PortfolioStressResponse, summary="Simulate macro stress test scenarios on paper portfolio")
async def get_portfolio_stress_test(
    account_id: str = Query("default_paper", description="Virtual paper account"),
    auth: AuthIdentity = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> PortfolioStressResponse:
    """Stress test current open positions against canonical macro shock events."""
    summary = await broker.get_portfolio_summary(db, account_id)

    base_cash = float(summary.cash_balance)
    base_equity = float(summary.total_equity)
    invested_capital = float(summary.invested_capital)

    scenarios_def = [
        (
            "btc_minus_20",
            "BTC -20% Macro Pullback",
            "Sharp Bitcoin liquidity drawdown. BTC -20%, large caps -25%, mid/altcoins -35%, memes -45%.",
        ),
        (
            "crypto_winter_45",
            "Systemic Crypto Winter Shock (-45%)",
            "Systemic market deleveraging event. BTC -45%, large caps -55%, altcoins -65%, memes -80%.",
        ),
        (
            "liquidity_crisis",
            "Orderbook Liquidity Drought & Flash Slippage",
            "Broad market -15% selloff combined with 500 bps liquidity execution penalty.",
        ),
        (
            "regulatory_alt_crackdown",
            "Regulatory Altcoin Flight to Bitcoin",
            "Capital concentrates into Bitcoin reserve. BTC +5%, all altcoins and memes -40%.",
        ),
        (
            "bull_breakout_30",
            "Bull Supercycle Breakout (+30%)",
            "Broad market upside expansion. BTC +30%, large caps +40%, altcoins +60%, memes +80%.",
        ),
    ]

    scenario_results: list[StressScenarioResult] = []

    for sc_id, sc_name, sc_desc in scenarios_def:
        pos_impacts: list[PositionStressImpact] = []
        total_impact_abs = 0.0

        for p in summary.open_positions:
            qty = float(p.quantity)
            curr_p = float(p.current_price)
            curr_val = float(p.market_value)

            shock_pct = _get_shock_percentage(p.symbol, sc_id)
            stressed_p = max(0.0, curr_p * (1.0 + shock_pct))
            stressed_val = max(0.0, curr_val * (1.0 + shock_pct))
            impact_usd = stressed_val - curr_val
            total_impact_abs += abs(impact_usd)

            pos_impacts.append(
                PositionStressImpact(
                    symbol=p.symbol,
                    side=p.side,
                    quantity=round(qty, 6),
                    current_price=round(curr_p, 4),
                    stressed_price=round(stressed_p, 4),
                    current_value_usd=round(curr_val, 2),
                    stressed_value_usd=round(stressed_val, 2),
                    impact_usd=round(impact_usd, 2),
                    impact_pct=round(shock_pct * 100.0, 2),
                    risk_contribution_pct=0.0,  # calculated below
                )
            )

        # Calculate risk contribution % per position
        for p_imp in pos_impacts:
            if total_impact_abs > 0:
                p_imp.risk_contribution_pct = round((abs(p_imp.impact_usd) / total_impact_abs) * 100.0, 2)

        total_impact_usd = sum(p.impact_usd for p in pos_impacts)
        stressed_equity = max(0.0, base_equity + total_impact_usd)
        drawdown_pct = round((total_impact_usd / base_equity) * 100.0, 2) if base_equity > 0 else 0.0

        scenario_results.append(
            StressScenarioResult(
                scenario_id=sc_id,
                name=sc_name,
                description=sc_desc,
                base_equity_usd=round(base_equity, 2),
                stressed_equity_usd=round(stressed_equity, 2),
                pnl_impact_usd=round(total_impact_usd, 2),
                drawdown_pct=drawdown_pct,
                position_impacts=pos_impacts,
            )
        )

    # Parametric 1-Day 95% Value-at-Risk estimation (assuming ~3.5% daily crypto vol)
    var_95_pct = 3.5 * 1.645 if summary.open_positions else 0.0
    var_95_usd = (base_equity * (var_95_pct / 100.0)) if base_equity > 0 else 0.0

    return PortfolioStressResponse(
        account_id=account_id,
        base_cash_usd=round(base_cash, 2),
        base_equity_usd=round(base_equity, 2),
        invested_capital_usd=round(invested_capital, 2),
        open_positions_count=len(summary.open_positions),
        var_95_daily_usd=round(var_95_usd, 2) if summary.open_positions else None,
        var_95_daily_pct=round(var_95_pct, 2) if summary.open_positions else None,
        scenarios=scenario_results,
        data_mode="HISTORICAL",
    )


@router.get("/sector-exposure", response_model=SectorExposureResponse, summary="Get portfolio sector allocation and concentration risk")
async def get_portfolio_sector_exposure(
    account_id: str = Query("default_paper", description="Virtual paper account"),
    auth: AuthIdentity = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> SectorExposureResponse:
    """Analyze sector exposure, Herfindahl concentration index, and position risk contributions."""
    summary = await broker.get_portfolio_summary(db, account_id)
    base_cash = float(summary.cash_balance)
    base_equity = float(summary.total_equity)
    invested_capital = float(summary.invested_capital)

    # Fetch asset sector registry
    asset_res = await db.execute(select(Asset.symbol, Asset.primary_sector, Asset.asset_class))
    sector_map = {row[0].upper(): row[1] for row in asset_res.all()}

    sector_totals: dict[str, dict[str, Any]] = {}
    total_position_val = sum(float(p.market_value) for p in summary.open_positions)

    risk_contribs: list[AssetRiskContribution] = []
    herfindahl_index = 0.0

    for p in summary.open_positions:
        sym = p.symbol.upper()
        sec = sector_map.get(sym, "Layer 1" if sym in {"BTC", "ETH", "SOL", "AVAX"} else "Altcoin")
        val = float(p.market_value)
        weight = (val / base_equity) if base_equity > 0 else 0.0
        herfindahl_index += weight**2

        if sec not in sector_totals:
            sector_totals[sec] = {"value": 0.0, "symbols": []}
        sector_totals[sec]["value"] += val
        sector_totals[sec]["symbols"].append(sym)

        pos_risk_pct = (val / total_position_val * 100.0) if total_position_val > 0 else 0.0
        risk_contribs.append(
            AssetRiskContribution(
                symbol=sym,
                sector=sec,
                market_value_usd=round(val, 2),
                weight_pct=round(weight * 100.0, 2),
                risk_contribution_pct=round(pos_risk_pct, 2),
            )
        )

    # Include Cash in sector breakdown if cash > 0
    sectors: list[SectorAllocationItem] = []
    for sec_name, sec_data in sector_totals.items():
        w_pct = (sec_data["value"] / base_equity * 100.0) if base_equity > 0 else 0.0
        sectors.append(
            SectorAllocationItem(
                sector=sec_name,
                value_usd=round(sec_data["value"], 2),
                weight_pct=round(w_pct, 2),
                symbols=sec_data["symbols"],
            )
        )

    if base_cash > 0:
        cash_weight = (base_cash / base_equity * 100.0) if base_equity > 0 else 0.0
        sectors.append(
            SectorAllocationItem(
                sector="Cash & Equivalents",
                value_usd=round(base_cash, 2),
                weight_pct=round(cash_weight, 2),
                symbols=["USDT"],
            )
        )

    gross_exposure_pct = round((invested_capital / base_equity * 100.0), 2) if base_equity > 0 else 0.0
    net_exposure_pct = gross_exposure_pct  # long-only paper trading in v3.0

    return SectorExposureResponse(
        account_id=account_id,
        total_equity_usd=round(base_equity, 2),
        cash_usd=round(base_cash, 2),
        invested_usd=round(invested_capital, 2),
        gross_exposure_pct=gross_exposure_pct,
        net_exposure_pct=net_exposure_pct,
        herfindahl_index=round(herfindahl_index, 6),
        is_concentrated=herfindahl_index > 0.25,
        sectors=sectors,
        risk_contributions=risk_contribs,
        data_mode="HISTORICAL",
    )
