"""Quantitative performance attribution and risk metrics for backtesting simulation."""

import math
from collections.abc import Sequence
from datetime import datetime
from typing import Any

import numpy as np

from src.backtesting.models import BacktestTradeRecord, EquityPoint


def calculate_cagr(
    start_equity: float,
    end_equity: float,
    start_date: datetime,
    end_date: datetime,
) -> float:
    """Calculate Compound Annual Growth Rate (CAGR).

    Returns percentage as a float (e.g., 25.5 for 25.5%).
    """
    if start_equity <= 0.0 or end_equity <= 0.0:
        return -100.0

    days = max(1.0, (end_date - start_date).total_seconds() / 86400.0)
    years = days / 365.25

    if years <= 0.0:
        return 0.0

    cagr_ratio = (end_equity / start_equity) ** (1.0 / years) - 1.0
    return float(cagr_ratio * 100.0)


def calculate_annualized_volatility(
    daily_returns: Sequence[float],
    periods_per_year: int = 365,
) -> float:
    """Calculate annualized volatility from periodic returns.

    Returns percentage as a float (e.g., 45.2 for 45.2%).
    """
    if len(daily_returns) < 2:
        return 0.0

    arr = np.array(daily_returns, dtype=np.float64)
    std = float(np.std(arr, ddof=1))
    if std <= 1e-9:
        return 0.0
    return float(std * math.sqrt(periods_per_year) * 100.0)


def calculate_sharpe_ratio(
    daily_returns: Sequence[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365,
) -> float:
    """Calculate annualized Sharpe Ratio."""
    if len(daily_returns) < 2:
        return 0.0

    arr = np.array(daily_returns, dtype=np.float64)
    rf_daily = risk_free_rate / periods_per_year
    excess_returns = arr - rf_daily

    std = float(np.std(excess_returns, ddof=1))
    if std <= 1e-9:
        return 0.0

    mean_excess = float(np.mean(excess_returns))
    return float((mean_excess / std) * math.sqrt(periods_per_year))


def calculate_sortino_ratio(
    daily_returns: Sequence[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365,
) -> float:
    """Calculate annualized Sortino Ratio (downside deviation denominator)."""
    if len(daily_returns) < 2:
        return 0.0

    arr = np.array(daily_returns, dtype=np.float64)
    rf_daily = risk_free_rate / periods_per_year
    excess_returns = arr - rf_daily

    downside = np.minimum(0.0, excess_returns)
    downside_variance = float(np.mean(downside**2))
    downside_std = math.sqrt(downside_variance)

    if downside_std <= 1e-9:
        return 0.0

    mean_excess = float(np.mean(excess_returns))
    return float((mean_excess / downside_std) * math.sqrt(periods_per_year))


def calculate_max_drawdown(
    equity_series: Sequence[float],
) -> tuple[float, int, int]:
    """Calculate Maximum Drawdown percentage and indices of peak and trough.

    Returns:
        (max_drawdown_pct, peak_index, trough_index)
        where max_drawdown_pct is positive (e.g., 18.5 for 18.5% drawdown).
    """
    if not equity_series or len(equity_series) < 2:
        return 0.0, 0, 0

    peak = equity_series[0]
    peak_idx = 0
    max_dd = 0.0
    best_peak_idx = 0
    trough_idx = 0

    for i, equity in enumerate(equity_series):
        if equity > peak:
            peak = equity
            peak_idx = i
        else:
            if peak > 0.0:
                dd = (peak - equity) / peak
                if dd > max_dd:
                    max_dd = dd
                    best_peak_idx = peak_idx
                    trough_idx = i

    return float(max_dd * 100.0), best_peak_idx, trough_idx


def calculate_drawdown_series(equity_series: Sequence[float]) -> list[float]:
    """Calculate underwater drawdown time series.

    Values are non-positive percentages, e.g. 0.0 at peaks, -12.4% during drawdowns.
    """
    if not equity_series:
        return []

    peak = equity_series[0]
    dd_series: list[float] = []

    for eq in equity_series:
        if eq > peak:
            peak = eq
        if peak > 0:
            dd = (eq - peak) / peak * 100.0
        else:
            dd = 0.0
        dd_series.append(float(dd))

    return dd_series


def calculate_calmar_ratio(cagr: float, max_drawdown_pct: float) -> float:
    """Calculate Calmar Ratio (CAGR / Max Drawdown)."""
    if max_drawdown_pct <= 1e-4:
        return float(cagr) if cagr > 0 else 0.0
    return float(cagr / max_drawdown_pct)


def calculate_trade_metrics(trades: Sequence[BacktestTradeRecord]) -> dict[str, float]:
    """Calculate complete trade distribution statistics."""
    if not trades:
        return {
            "total_trades": 0.0,
            "winning_trades": 0.0,
            "losing_trades": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "total_pnl_usd": 0.0,
            "total_fees_usd": 0.0,
            "total_slippage_usd": 0.0,
            "avg_trade_pnl_usd": 0.0,
            "avg_win_usd": 0.0,
            "avg_loss_usd": 0.0,
            "payoff_ratio": 0.0,
            "expectancy_usd": 0.0,
            "max_consecutive_losses": 0.0,
        }

    total_trades = len(trades)
    pnls = [t.pnl_usd for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 1e-9 else (99.0 if gross_profit > 0 else 0.0)

    win_rate = (len(wins) / total_trades) * 100.0
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = abs(float(np.mean(losses))) if losses else 0.0
    payoff_ratio = (avg_win / avg_loss) if avg_loss > 1e-9 else (avg_win if avg_win > 0 else 0.0)

    win_prob = len(wins) / total_trades
    loss_prob = len(losses) / total_trades
    expectancy = (win_prob * avg_win) - (loss_prob * avg_loss)

    # Max consecutive losses
    curr_loss_streak = 0
    max_loss_streak = 0
    for p in pnls:
        if p <= 0:
            curr_loss_streak += 1
            if curr_loss_streak > max_loss_streak:
                max_loss_streak = curr_loss_streak
        else:
            curr_loss_streak = 0

    return {
        "total_trades": float(total_trades),
        "winning_trades": float(len(wins)),
        "losing_trades": float(len(losses)),
        "win_rate": float(round(win_rate, 2)),
        "profit_factor": float(round(profit_factor, 2)),
        "total_pnl_usd": float(round(sum(pnls), 2)),
        "total_fees_usd": float(round(sum(t.fees_usd for t in trades), 2)),
        "total_slippage_usd": float(round(sum(t.slippage_usd for t in trades), 2)),
        "avg_trade_pnl_usd": float(round(float(np.mean(pnls)), 2)),
        "avg_win_usd": float(round(avg_win, 2)),
        "avg_loss_usd": float(round(avg_loss, 2)),
        "payoff_ratio": float(round(payoff_ratio, 2)),
        "expectancy_usd": float(round(expectancy, 2)),
        "max_consecutive_losses": float(max_loss_streak),
    }


TIMEFRAME_PERIODS_PER_YEAR: dict[str, int] = {
    "1m": 525600,
    "3m": 175200,
    "5m": 105120,
    "15m": 35040,
    "30m": 17520,
    "1h": 8760,
    "2h": 4380,
    "4h": 2190,
    "6h": 1460,
    "8h": 1095,
    "12h": 730,
    "1d": 365,
    "d": 365,
    "daily": 365,
    "1w": 52,
    "w": 52,
    "weekly": 52,
}


def periods_per_year_from_timeframe(timeframe: str | None = None, default: int = 365) -> int:
    """Derive annual periods count from candle timeframe string (e.g. 1h -> 8760, 1d -> 365)."""
    if not timeframe:
        return default
    return TIMEFRAME_PERIODS_PER_YEAR.get(timeframe.lower().strip(), default)


def compute_complete_metrics(
    equity_curve: list[EquityPoint],
    trades: list[BacktestTradeRecord],
    start_date: datetime,
    end_date: datetime,
    timeframe: str | None = None,
    periods_per_year: int | None = None,
) -> dict[str, Any]:
    """Calculate comprehensive performance, risk, and attribution metrics for backtest."""
    if not equity_curve:
        return {}

    # Resolve annualization periods per year
    if periods_per_year is None:
        if timeframe is not None:
            periods_per_year = periods_per_year_from_timeframe(timeframe)
        elif len(equity_curve) >= 2:
            deltas = [
                (equity_curve[i].time - equity_curve[i - 1].time).total_seconds()
                for i in range(1, len(equity_curve))
            ]
            median_delta = float(np.median(deltas)) if deltas else 86400.0
            if median_delta > 0:
                if abs(median_delta - 3600.0) < 60:
                    periods_per_year = 8760
                elif abs(median_delta - 86400.0) < 300:
                    periods_per_year = 365
                elif abs(median_delta - 14400.0) < 120:
                    periods_per_year = 2190
                else:
                    periods_per_year = max(1, int(round((365.25 * 86400.0) / median_delta)))
            else:
                periods_per_year = 365
        else:
            periods_per_year = 365

    initial_equity = equity_curve[0].equity
    final_equity = equity_curve[-1].equity
    total_return_pct = ((final_equity - initial_equity) / initial_equity) * 100.0

    benchmark_initial = equity_curve[0].benchmark_equity
    benchmark_final = equity_curve[-1].benchmark_equity
    benchmark_return_pct = (
        ((benchmark_final - benchmark_initial) / benchmark_initial) * 100.0 if benchmark_initial > 0 else 0.0
    )

    equity_values = [p.equity for p in equity_curve]
    daily_returns: list[float] = []
    for i in range(1, len(equity_values)):
        prev = equity_values[i - 1]
        curr = equity_values[i]
        ret = (curr - prev) / prev if prev > 0 else 0.0
        daily_returns.append(ret)

    cagr = calculate_cagr(initial_equity, final_equity, start_date, end_date)
    volatility = calculate_annualized_volatility(daily_returns, periods_per_year=periods_per_year)
    sharpe = calculate_sharpe_ratio(daily_returns, periods_per_year=periods_per_year)
    sortino = calculate_sortino_ratio(daily_returns, periods_per_year=periods_per_year)
    max_dd, _, _ = calculate_max_drawdown(equity_values)
    calmar = calculate_calmar_ratio(cagr, max_dd)

    # Benchmark metrics
    benchmark_returns: list[float] = []
    bm_values = [p.benchmark_equity for p in equity_curve]
    for i in range(1, len(bm_values)):
        prev = bm_values[i - 1]
        curr = bm_values[i]
        ret = (curr - prev) / prev if prev > 0 else 0.0
        benchmark_returns.append(ret)

    # Beta and Alpha calculation
    beta = 1.0
    alpha_pct = 0.0
    if len(daily_returns) > 5 and len(benchmark_returns) == len(daily_returns):
        cov = float(np.cov(daily_returns, benchmark_returns)[0, 1])
        var_bm = float(np.var(benchmark_returns, ddof=1))
        if var_bm > 1e-9:
            beta = cov / var_bm
            alpha_pct = (cagr - (beta * benchmark_return_pct))

    trade_stats = calculate_trade_metrics(trades)

    metrics: dict[str, Any] = {
        "initial_capital": round(initial_equity, 2),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return_pct, 2),
        "benchmark_return_pct": round(benchmark_return_pct, 2),
        "excess_return_pct": round(total_return_pct - benchmark_return_pct, 2),
        "cagr": round(cagr, 2),
        "annualized_volatility": round(volatility, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "calmar_ratio": round(calmar, 2),
        "beta": round(beta, 2),
        "alpha_pct": round(alpha_pct, 2),
        "periods_per_year": periods_per_year,
    }

    metrics.update(trade_stats)
    return metrics
