"""Market regime classification engine (RISK_ON, NEUTRAL, RISK_OFF)."""

from collections.abc import Mapping, Sequence

import numpy as np
from pydantic import BaseModel

from src.config.constants import MarketRegime
from src.features.relative_strength import calculate_ema


class MarketRegimeClassification(BaseModel):
    """Point-in-time market regime classification."""
    regime: MarketRegime
    confidence: float  # 0.0 to 1.0
    btc_above_ema50: bool
    btc_above_ema200: bool
    btc_trend_slope: float
    market_breadth_pct: float
    eth_btc_ratio_trend: float
    funding_sentiment: str  # BULLISH, NEUTRAL, BEARISH
    rationale: list[str]


def classify_market_regime(
    btc_closes: Sequence[float],
    eth_closes: Sequence[float] | None = None,
    universe_closes: Mapping[str, Sequence[float]] | None = None,
    aggregate_funding_rate: float | None = None,
    candles_per_day: int = 24,
) -> MarketRegimeClassification:
    """
    Classify macro market state into RISK_ON, NEUTRAL, or RISK_OFF.
    Strictly point-in-time calculation for historical backtest reproduction.
    """
    btc_arr = np.array(btc_closes, dtype=np.float64)
    n = len(btc_arr)
    if n < 50:
        return MarketRegimeClassification(
            regime=MarketRegime.NEUTRAL,
            confidence=0.5,
            btc_above_ema50=False,
            btc_above_ema200=False,
            btc_trend_slope=0.0,
            market_breadth_pct=50.0,
            eth_btc_ratio_trend=0.0,
            funding_sentiment="NEUTRAL",
            rationale=["INSUFFICIENT_HISTORICAL_DATA"],
        )

    last_btc = btc_arr[-1]

    # 1. BTC Trend vs EMAs
    ema50 = calculate_ema(btc_arr, min(n, int(50 * candles_per_day / 24)))[-1]
    ema200 = calculate_ema(btc_arr, min(n, int(200 * candles_per_day / 24)))[-1] if n >= 200 else ema50

    btc_above_ema50 = bool(last_btc > ema50) if not np.isnan(ema50) else False
    btc_above_ema200 = bool(last_btc > ema200) if not np.isnan(ema200) else False

    # Slope over last 7 days
    p7 = min(n - 1, int(7 * candles_per_day))
    btc_slope = float((last_btc - btc_arr[-p7 - 1]) / btc_arr[-p7 - 1]) if p7 > 0 and btc_arr[-p7 - 1] > 0 else 0.0

    # 2. Market Breadth: % of universe coins with positive 7D return
    breadth_pct = 50.0
    if universe_closes and len(universe_closes) > 0:
        positive_count = 0
        total_valid = 0
        for _sym, c_seq in universe_closes.items():
            arr = np.array(c_seq, dtype=np.float64)
            if len(arr) > p7 and arr[-p7 - 1] > 0:
                ret7 = (arr[-1] - arr[-p7 - 1]) / arr[-p7 - 1]
                if ret7 > 0:
                    positive_count += 1
                total_valid += 1
        if total_valid > 0:
            breadth_pct = float((positive_count / total_valid) * 100.0)

    # 3. ETH/BTC ratio trend
    eth_btc_trend = 0.0
    if eth_closes and len(eth_closes) == n:
        eth_arr = np.array(eth_closes, dtype=np.float64)
        if btc_arr[-1] > 0 and btc_arr[-p7 - 1] > 0 and eth_arr[-p7 - 1] > 0:
            curr_ratio = eth_arr[-1] / btc_arr[-1]
            prior_ratio = eth_arr[-p7 - 1] / btc_arr[-p7 - 1]
            eth_btc_trend = float((curr_ratio - prior_ratio) / prior_ratio)

    # 4. Derivative Funding Sentiment
    funding_sentiment = "NEUTRAL"
    if aggregate_funding_rate is not None:
        if aggregate_funding_rate > 0.0003:  # > 0.03% per 8h is elevated
            funding_sentiment = "BULLISH"
        elif aggregate_funding_rate < -0.0001:  # negative funding
            funding_sentiment = "BEARISH"

    # Multi-factor score aggregation
    score = 0
    rationale: list[str] = []

    if btc_above_ema50:
        score += 2
        rationale.append("BTC > EMA50")
    else:
        score -= 2
        rationale.append("BTC < EMA50")

    if btc_above_ema200:
        score += 1
        rationale.append("BTC > EMA200")
    else:
        score -= 1
        rationale.append("BTC < EMA200")

    if breadth_pct >= 60.0:
        score += 2
        rationale.append(f"Strong Market Breadth ({breadth_pct:.1f}%)")
    elif breadth_pct <= 40.0:
        score -= 2
        rationale.append(f"Weak Market Breadth ({breadth_pct:.1f}%)")

    if eth_btc_trend > 0.02:
        score += 1
        rationale.append("ETH/BTC expanding (altcoin appetite)")
    elif eth_btc_trend < -0.02:
        score -= 1
        rationale.append("ETH/BTC contracting (risk aversion)")

    if score >= 3:
        regime = MarketRegime.RISK_ON
        confidence = min(0.95, 0.6 + (score * 0.07))
    elif score <= -2:
        regime = MarketRegime.RISK_OFF
        confidence = min(0.95, 0.6 + (abs(score) * 0.07))
    else:
        regime = MarketRegime.NEUTRAL
        confidence = 0.60

    return MarketRegimeClassification(
        regime=regime,
        confidence=round(confidence, 2),
        btc_above_ema50=btc_above_ema50,
        btc_above_ema200=btc_above_ema200,
        btc_trend_slope=round(btc_slope, 4),
        market_breadth_pct=round(breadth_pct, 1),
        eth_btc_ratio_trend=round(eth_btc_trend, 4),
        funding_sentiment=funding_sentiment,
        rationale=rationale,
    )
