"""Vectorized trend indicator calculations (EMAs, MACD, ADX, ATR)."""

from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel

from src.features.relative_strength import calculate_ema


class TrendMetrics(BaseModel):
    """Calculated trend and market structure indicators."""
    ema20_ratio: float | None = None
    ema50_ratio: float | None = None
    ema200_ratio: float | None = None
    trend_alignment_score: int | None = None  # 0 to 3
    adx_14: float | None = None
    macd_line: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    atr_14: float | None = None
    atr_14_pct: float | None = None


def calculate_atr(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """Calculate Average True Range array using Wilder's smoothing."""
    n = len(closes)
    if n < 2:
        return np.array([np.nan] * n)

    tr = np.zeros(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, hc, lc)

    if n < period:
        return tr

    atr = np.zeros(n)
    atr[period - 1] = np.mean(tr[:period])
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def calculate_adx(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 14,
) -> float | None:
    """Calculate Average Directional Index (ADX) at the latest candle."""
    n = len(closes)
    if n < period * 2:
        return None

    atr = calculate_atr(highs, lows, closes, period)
    if len(atr) == 0 or np.isnan(atr[-1]) or atr[-1] == 0:
        return None

    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)

    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]

        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move

    # Wilder's smoothing for DM
    smoothed_plus_dm = np.zeros(n)
    smoothed_minus_dm = np.zeros(n)
    smoothed_plus_dm[period - 1] = np.mean(plus_dm[:period])
    smoothed_minus_dm[period - 1] = np.mean(minus_dm[:period])

    for i in range(period, n):
        smoothed_plus_dm[i] = (smoothed_plus_dm[i - 1] * (period - 1) + plus_dm[i]) / period
        smoothed_minus_dm[i] = (smoothed_minus_dm[i - 1] * (period - 1) + minus_dm[i]) / period

    dx = np.zeros(n)
    for i in range(period - 1, n):
        if atr[i] > 0:
            plus_di = (smoothed_plus_dm[i] / atr[i]) * 100.0
            minus_di = (smoothed_minus_dm[i] / atr[i]) * 100.0
            di_sum = plus_di + minus_di
            if di_sum > 0:
                dx[i] = (abs(plus_di - minus_di) / di_sum) * 100.0

    adx_arr = np.zeros(n)
    adx_start = (period * 2) - 1
    if n <= adx_start:
        return None

    adx_arr[adx_start] = np.mean(dx[period - 1 : adx_start + 1])
    for i in range(adx_start + 1, n):
        adx_arr[i] = (adx_arr[i - 1] * (period - 1) + dx[i]) / period

    return float(adx_arr[-1])


def calculate_trend_features(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> TrendMetrics:
    """Calculate comprehensive trend indicators strictly using historical candles."""
    c_arr = np.array(closes, dtype=np.float64)
    h_arr = np.array(highs, dtype=np.float64)
    l_arr = np.array(lows, dtype=np.float64)
    n = len(c_arr)

    if n < 20:
        return TrendMetrics()

    last_close = c_arr[-1]

    # EMAs
    ema20 = calculate_ema(c_arr, 20)[-1]
    ema50 = calculate_ema(c_arr, 50)[-1] if n >= 50 else np.nan
    ema200 = calculate_ema(c_arr, 200)[-1] if n >= 200 else np.nan

    ema20_ratio = float(last_close / ema20) if not np.isnan(ema20) and ema20 > 0 else None
    ema50_ratio = float(last_close / ema50) if not np.isnan(ema50) and ema50 > 0 else None
    ema200_ratio = float(last_close / ema200) if not np.isnan(ema200) and ema200 > 0 else None

    # Trend Alignment Score (0 to 3)
    alignment = 0
    if not np.isnan(ema20) and last_close > ema20:
        alignment += 1
    if not np.isnan(ema20) and not np.isnan(ema50) and ema20 > ema50:
        alignment += 1
    if not np.isnan(ema50) and not np.isnan(ema200) and ema50 > ema200:
        alignment += 1

    # MACD (12, 26, 9)
    macd_line: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    if n >= 26:
        ema12 = calculate_ema(c_arr, 12)
        ema26 = calculate_ema(c_arr, 26)
        macd_series = ema12 - ema26
        macd_line = float(macd_series[-1])
        if n >= 35:
            signal_series = calculate_ema(macd_series, 9)
            macd_signal = float(signal_series[-1])
            macd_hist = float(macd_line - macd_signal)

    # ATR 14
    atr_val: float | None = None
    atr_pct: float | None = None
    if n >= 14:
        atr_series = calculate_atr(h_arr, l_arr, c_arr, 14)
        atr_val = float(atr_series[-1])
        if last_close > 0:
            atr_pct = float((atr_val / last_close) * 100.0)

    # ADX 14
    adx_val = calculate_adx(h_arr, l_arr, c_arr, 14)

    return TrendMetrics(
        ema20_ratio=ema20_ratio,
        ema50_ratio=ema50_ratio,
        ema200_ratio=ema200_ratio,
        trend_alignment_score=alignment,
        adx_14=adx_val,
        macd_line=macd_line,
        macd_signal=macd_signal,
        macd_histogram=macd_hist,
        atr_14=atr_val,
        atr_14_pct=atr_pct,
    )
