"use client";

import React from "react";
import { formatPercent, EMPTY_FALLBACK } from "@/lib/format";

export interface DecileBarData {
  decile: number;
  mean_forward_return_pct: number;
  sample_size: number;
  score_min?: number;
  score_max?: number;
}

interface DecileBarChartProps {
  deciles?: DecileBarData[];
  monotonicitySpreadPct?: number;
  horizon?: string;
  className?: string;
}

export function DecileBarChart({
  deciles = [],
  monotonicitySpreadPct,
  horizon = "1d",
  className = "",
}: DecileBarChartProps) {
  if (!deciles || deciles.length === 0) {
    return (
      <div className={`rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center ${className}`}>
        <p className="text-xs text-[var(--text-dim)]">Awaiting decile forward return data...</p>
      </div>
    );
  }

  // Find max absolute return to symmetrically scale bars
  const returns = deciles.map((d) => d.mean_forward_return_pct);
  const maxAbs = Math.max(1.0, Math.max(...returns.map(Math.abs)) * 1.25);

  const getBarColor = (decile: number, val: number) => {
    if (val < 0) {
      if (decile <= 3) return "bg-rose-500/80 border-rose-400";
      return "bg-rose-400/60 border-rose-300";
    }
    if (decile >= 8) return "bg-emerald-500/90 border-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.3)]";
    if (decile >= 5) return "bg-sky-500/70 border-sky-400";
    return "bg-slate-500/60 border-slate-400";
  };

  return (
    <div
      className={`rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 ${className}`}
      role="region"
      aria-label="Decile Forward Return Profile"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-3 border-b border-[var(--border-subtle)] gap-2">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
              Forward Return by Score Decile (D1 – D10)
            </h3>
            <span className="text-[10px] px-1.5 py-0.5 rounded font-mono bg-sky-500/10 text-sky-400 border border-sky-500/20">
              Horizon: {horizon.toUpperCase()}
            </span>
          </div>
          <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
            Monotonicity profile: higher opportunity scores should consistently out-earn lower deciles.
          </p>
        </div>

        {monotonicitySpreadPct !== undefined && (
          <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs font-mono">
            <span className="text-[var(--text-dim)]">Spread (D10 - D1):</span>
            <span
              className={`font-bold ${
                monotonicitySpreadPct > 0
                  ? "text-emerald-400"
                  : monotonicitySpreadPct < 0
                  ? "text-rose-400"
                  : "text-white"
              }`}
            >
              {formatPercent(monotonicitySpreadPct, { isFraction: false })}
            </span>
          </div>
        )}
      </div>

      {/* Decile Vertical Bar Grid */}
      <div className="grid grid-cols-10 gap-2 h-44 items-end pt-6 pb-2 px-1 relative">
        {/* Zero baseline */}
        <div className="absolute left-0 right-0 top-1/2 -translate-y-1/2 border-b border-dashed border-[var(--border-subtle)] pointer-events-none" />

        {deciles.map((d) => {
          const val = d.mean_forward_return_pct;
          const heightPct = Math.min(100, (Math.abs(val) / maxAbs) * 100);
          const isPositive = val >= 0;

          return (
            <div
              key={`decile-${d.decile}`}
              className="flex flex-col items-center justify-end h-full group relative"
            >
              {/* Tooltip on hover */}
              <div className="absolute -top-10 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-20 bg-[var(--bg-card)] border border-[var(--border-subtle)] px-2 py-1 rounded text-[10px] font-mono whitespace-nowrap shadow-lg">
                <span className="font-bold text-white">D{d.decile}</span>:{" "}
                <span className={val >= 0 ? "text-emerald-400" : "text-rose-400"}>
                  {formatPercent(val, { isFraction: false })}
                </span>{" "}
                (N={d.sample_size})
              </div>

              {/* Bar Value Label */}
              <div
                className={`text-[10px] font-mono font-bold mb-1 transition-transform group-hover:scale-110 ${
                  val > 0 ? "text-emerald-400" : val < 0 ? "text-rose-400" : "text-[var(--text-dim)]"
                }`}
              >
                {formatPercent(val, { isFraction: false, decimals: 1 })}
              </div>

              {/* Bar Container */}
              <div className="w-full flex-1 flex flex-col justify-center items-center">
                <div
                  style={{ height: `${Math.max(4, heightPct / 2)}%` }}
                  className={`w-full max-w-[28px] rounded-t-sm border-t transition-all ${getBarColor(
                    d.decile,
                    val
                  )}`}
                />
              </div>

              {/* Decile Label */}
              <div className="mt-2 text-center">
                <span className="text-[11px] font-mono font-semibold text-white block">
                  D{d.decile}
                </span>
                <span className="text-[9px] font-mono text-[var(--text-dim)] block">
                  N={d.sample_size}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
