"use client";

import React, { useState } from "react";
import { Info, HelpCircle } from "lucide-react";
import { formatPercent, EMPTY_FALLBACK } from "@/lib/format";

export interface FeatureRecord {
  return_1d?: number | null;
  return_3d?: number | null;
  return_7d?: number | null;
  return_14d?: number | null;
  return_30d?: number | null;
  return_90d?: number | null;
  momentum_acceleration?: number | null;
  volatility_adjusted_momentum?: number | null;
  rs_btc_30d?: number | null;
  rs_eth_30d?: number | null;
  rs_sector_30d?: number | null;
  ema20_ratio?: number | null;
  ema50_ratio?: number | null;
  ema200_ratio?: number | null;
  adx_14?: number | null;
  atr_14_pct?: number | null;
  volume_to_20d_avg?: number | null;
  volume_acceleration?: number | null;
  turnover_ratio?: number | null;
  spread_est_bps?: number | null;
  realized_vol_30d?: number | null;
  downside_vol_30d?: number | null;
  max_drawdown_90d?: number | null;
}

interface FeatureGlossaryTableProps {
  features?: FeatureRecord | null;
  className?: string;
}

interface FeatureMeta {
  key: keyof FeatureRecord;
  name: string;
  category: "Momentum" | "Trend" | "Relative Strength" | "Liquidity" | "Risk";
  format: (v: number | null | undefined) => string;
  glossary: string;
  signalRule: (v: number | null | undefined) => "positive" | "negative" | "neutral";
}

const FEATURE_METADATA: FeatureMeta[] = [
  // Momentum
  {
    key: "return_1d",
    name: "1D Trailing Return",
    category: "Momentum",
    format: (v) => formatPercent(v, { isFraction: true }),
    glossary: "Trailing 24-hour price change calculated on hourly close prices.",
    signalRule: (v) => (v ? (v > 0 ? "positive" : "negative") : "neutral"),
  },
  {
    key: "return_7d",
    name: "7D Trailing Return",
    category: "Momentum",
    format: (v) => formatPercent(v, { isFraction: true }),
    glossary: "Trailing 7-day cyclical return across 168 hourly intervals.",
    signalRule: (v) => (v ? (v > 0 ? "positive" : "negative") : "neutral"),
  },
  {
    key: "return_30d",
    name: "30D Trailing Return",
    category: "Momentum",
    format: (v) => formatPercent(v, { isFraction: true }),
    glossary: "Trailing 30-day primary momentum anchor.",
    signalRule: (v) => (v ? (v > 0 ? "positive" : "negative") : "neutral"),
  },
  {
    key: "momentum_acceleration",
    name: "Momentum Acceleration",
    category: "Momentum",
    format: (v) => (v !== null && v !== undefined ? `${v > 0 ? "+" : ""}${v.toFixed(3)}/d` : EMPTY_FALLBACK),
    glossary: "Rate of change of the 7D return relative to the 30D baseline (convexity signal).",
    signalRule: (v) => (v ? (v > 0 ? "positive" : "negative") : "neutral"),
  },
  {
    key: "volatility_adjusted_momentum",
    name: "Vol-Adjusted Momentum",
    category: "Momentum",
    format: (v) => (v !== null && v !== undefined ? v.toFixed(2) : EMPTY_FALLBACK),
    glossary: "30D return normalized by 30D realized volatility (Sharpe proxy for trend strength).",
    signalRule: (v) => (v ? (v > 1.0 ? "positive" : v < 0 ? "negative" : "neutral") : "neutral"),
  },

  // Relative Strength
  {
    key: "rs_btc_30d",
    name: "Relative Strength vs BTC",
    category: "Relative Strength",
    format: (v) => formatPercent(v, { isFraction: true }),
    glossary: "30-day return minus Bitcoin benchmark return. Positive indicates crypto beta outperformance.",
    signalRule: (v) => (v ? (v > 0 ? "positive" : "negative") : "neutral"),
  },
  {
    key: "rs_eth_30d",
    name: "Relative Strength vs ETH",
    category: "Relative Strength",
    format: (v) => formatPercent(v, { isFraction: true }),
    glossary: "30-day return minus Ethereum benchmark return. Tracks altcoin leadership.",
    signalRule: (v) => (v ? (v > 0 ? "positive" : "negative") : "neutral"),
  },
  {
    key: "rs_sector_30d",
    name: "Relative Strength vs Sector",
    category: "Relative Strength",
    format: (v) => formatPercent(v, { isFraction: true }),
    glossary: "Asset 30-day return minus aggregate sector benchmark return (intra-sector alpha).",
    signalRule: (v) => (v ? (v > 0 ? "positive" : "negative") : "neutral"),
  },

  // Trend
  {
    key: "ema20_ratio",
    name: "Price / EMA 20 Ratio",
    category: "Trend",
    format: (v) => (v !== null && v !== undefined ? `${v.toFixed(3)}x` : EMPTY_FALLBACK),
    glossary: "Current price divided by 20-period Exponential Moving Average. >1.00 indicates short-term uptrend.",
    signalRule: (v) => (v ? (v >= 1.0 ? "positive" : "negative") : "neutral"),
  },
  {
    key: "ema50_ratio",
    name: "Price / EMA 50 Ratio",
    category: "Trend",
    format: (v) => (v !== null && v !== undefined ? `${v.toFixed(3)}x` : EMPTY_FALLBACK),
    glossary: "Current price divided by 50-period EMA. Medium-term trend filter.",
    signalRule: (v) => (v ? (v >= 1.0 ? "positive" : "negative") : "neutral"),
  },
  {
    key: "ema200_ratio",
    name: "Price / EMA 200 Ratio",
    category: "Trend",
    format: (v) => (v !== null && v !== undefined ? `${v.toFixed(3)}x` : EMPTY_FALLBACK),
    glossary: "Current price divided by 200-period EMA. Primary macro bull/bear boundary.",
    signalRule: (v) => (v ? (v >= 1.0 ? "positive" : "negative") : "neutral"),
  },
  {
    key: "adx_14",
    name: "ADX (14)",
    category: "Trend",
    format: (v) => (v !== null && v !== undefined ? v.toFixed(1) : EMPTY_FALLBACK),
    glossary: "Average Directional Index over 14 periods. >25 indicates trending; <20 indicates chop.",
    signalRule: (v) => (v ? (v >= 25 ? "positive" : "neutral") : "neutral"),
  },
  {
    key: "atr_14_pct",
    name: "ATR % (14)",
    category: "Trend",
    format: (v) => formatPercent(v, { isFraction: true }),
    glossary: "Average True Range as a percentage of price. Primary volatility filter for stop sizing.",
    signalRule: () => "neutral",
  },

  // Liquidity
  {
    key: "volume_to_20d_avg",
    name: "Volume / 20D Average (RVOL)",
    category: "Liquidity",
    format: (v) => (v !== null && v !== undefined ? `${v.toFixed(2)}x` : EMPTY_FALLBACK),
    glossary: "Current volume relative to the 20-day moving average. >1.5x signals institutional participation.",
    signalRule: (v) => (v ? (v >= 1.5 ? "positive" : "neutral") : "neutral"),
  },
  {
    key: "spread_est_bps",
    name: "Estimated Spread (bps)",
    category: "Liquidity",
    format: (v) => (v !== null && v !== undefined ? `${v.toFixed(1)} bps` : EMPTY_FALLBACK),
    glossary: "Estimated bid-ask spread in basis points derived from high-low volatility.",
    signalRule: (v) => (v ? (v <= 15 ? "positive" : v >= 50 ? "negative" : "neutral") : "neutral"),
  },
  {
    key: "turnover_ratio",
    name: "Turnover Ratio",
    category: "Liquidity",
    format: (v) => (v !== null && v !== undefined ? `${(v * 100).toFixed(2)}%` : EMPTY_FALLBACK),
    glossary: "24-hour volume divided by market liquidity depth.",
    signalRule: () => "neutral",
  },

  // Risk
  {
    key: "realized_vol_30d",
    name: "30D Realized Volatility",
    category: "Risk",
    format: (v) => formatPercent(v, { isFraction: true }),
    glossary: "Annualized standard deviation of hourly log returns over 30 days.",
    signalRule: (v) => (v ? (v > 1.0 ? "negative" : "neutral") : "neutral"),
  },
  {
    key: "downside_vol_30d",
    name: "30D Downside Volatility",
    category: "Risk",
    format: (v) => formatPercent(v, { isFraction: true }),
    glossary: "Semi-variance of negative price moves. Basis for the Sortino ratio.",
    signalRule: (v) => (v ? (v > 0.8 ? "negative" : "neutral") : "neutral"),
  },
  {
    key: "max_drawdown_90d",
    name: "90D Max Drawdown",
    category: "Risk",
    format: (v) => formatPercent(v, { isFraction: true }),
    glossary: "Peak-to-trough decline over the trailing 90-day window.",
    signalRule: (v) => (v ? (v < -0.3 ? "negative" : "neutral") : "neutral"),
  },
];

export function FeatureGlossaryTable({
  features,
  className = "",
}: FeatureGlossaryTableProps) {
  const [activeCategory, setActiveCategory] = useState<string>("ALL");
  const [tooltipItem, setTooltipItem] = useState<FeatureMeta | null>(null);

  const categories = ["ALL", "Momentum", "Trend", "Relative Strength", "Liquidity", "Risk"];

  const filteredFeatures = FEATURE_METADATA.filter(
    (f) => activeCategory === "ALL" || f.category === activeCategory
  );

  return (
    <div
      className={`rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 flex flex-col ${className}`}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-3 border-b border-[var(--border-subtle)] gap-2">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
            Quantitative Feature Telemetry
          </h3>
          <p className="text-[11px] text-[var(--text-muted)]">
            Computed technical, liquidity, and relative strength vectors.
          </p>
        </div>

        {/* Category Tabs */}
        <div className="flex flex-wrap items-center gap-1">
          {categories.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setActiveCategory(cat)}
              className={`px-2 py-0.5 rounded text-[10px] font-mono transition ${
                activeCategory === cat
                  ? "bg-sky-500/20 text-sky-300 font-semibold border border-sky-500/30"
                  : "bg-[var(--bg-card)] text-[var(--text-muted)] hover:text-white border border-[var(--border-subtle)]"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Feature Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead>
            <tr className="border-b border-[var(--border-subtle)] text-[10px] text-[var(--text-dim)] uppercase">
              <th className="py-2 px-3 font-semibold">Feature Metric</th>
              <th className="py-2 px-3 font-semibold">Category</th>
              <th className="py-2 px-3 font-semibold text-right">Value</th>
              <th className="py-2 px-3 font-semibold text-center w-12">Signal</th>
              <th className="py-2 px-3 font-semibold text-center w-10">Info</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-subtle)]">
            {filteredFeatures.map((item) => {
              const val = features ? features[item.key] : null;
              const formattedVal = item.format(val);
              const signal = item.signalRule(val);

              return (
                <tr
                  key={item.key}
                  className="hover:bg-[var(--bg-card)]/40 transition group"
                >
                  <td className="py-2 px-3 font-medium text-white flex items-center gap-1.5">
                    <span>{item.name}</span>
                  </td>
                  <td className="py-2 px-3 text-[10px] text-[var(--text-dim)]">
                    {item.category}
                  </td>
                  <td className="py-2 px-3 text-right font-bold text-white">
                    {formattedVal}
                  </td>
                  <td className="py-2 px-3 text-center">
                    {signal === "positive" ? (
                      <span className="inline-block w-2 h-2 rounded-full bg-emerald-400" title="Bullish bias" />
                    ) : signal === "negative" ? (
                      <span className="inline-block w-2 h-2 rounded-full bg-rose-400" title="Defensive bias" />
                    ) : (
                      <span className="inline-block w-2 h-2 rounded-full bg-slate-600" title="Neutral" />
                    )}
                  </td>
                  <td className="py-2 px-3 text-center relative">
                    <button
                      type="button"
                      onClick={() => setTooltipItem(tooltipItem?.key === item.key ? null : item)}
                      className="p-1 rounded text-[var(--text-dim)] hover:text-sky-400 transition"
                      title={item.glossary}
                    >
                      <HelpCircle className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Glossary Info Box if active item clicked */}
      {tooltipItem && (
        <div className="mt-3 p-3 rounded-[var(--radius-sm)] bg-sky-500/10 border border-sky-500/20 text-xs text-sky-200 flex items-start justify-between gap-3">
          <div>
            <strong className="block text-white font-mono mb-0.5">
              {tooltipItem.name} ({tooltipItem.category})
            </strong>
            <p className="text-[11px] text-sky-200/90">{tooltipItem.glossary}</p>
          </div>
          <button
            type="button"
            onClick={() => setTooltipItem(null)}
            className="text-[10px] text-sky-400 hover:text-white font-mono uppercase"
          >
            Close
          </button>
        </div>
      )}
    </div>
  );
}
