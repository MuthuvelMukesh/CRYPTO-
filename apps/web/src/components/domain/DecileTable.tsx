"use client";

import React from "react";
import { formatPercent, formatNumber, EMPTY_FALLBACK } from "@/lib/format";
import { AlertCircle } from "lucide-react";

export interface DecileRow {
  decile: number;
  score_min: number;
  score_max: number;
  sample_size: number;
  mean_forward_return_pct: number;
  median_forward_return_pct: number;
  std_forward_return_pct: number;
  annualized_return_pct: number;
  positive_return_ratio: number;
}

interface DecileTableProps {
  deciles?: DecileRow[];
  minSamplesThreshold?: number;
  className?: string;
}

export function DecileTable({
  deciles = [],
  minSamplesThreshold = 30,
  className = "",
}: DecileTableProps) {
  if (!deciles || deciles.length === 0) {
    return (
      <div className={`rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center ${className}`}>
        <p className="text-xs text-[var(--text-dim)]">No decile data available for current horizon.</p>
      </div>
    );
  }

  return (
    <div className={`rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] overflow-hidden ${className}`}>
      <div className="p-3.5 border-b border-[var(--border-subtle)] flex items-center justify-between">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
            Score Decile Statistical Breakdown
          </h3>
          <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
            Parametric and non-parametric forward return moments across opportunity score deciles.
          </p>
        </div>
        <span className="text-[10px] font-mono text-[var(--text-dim)]">
          10 Buckets (D1 lowest - D10 highest)
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead className="text-[10px] uppercase text-[var(--text-dim)] bg-[var(--bg-card)]/50 border-b border-[var(--border-subtle)]">
            <tr>
              <th className="py-2.5 px-3 font-semibold">Decile</th>
              <th className="py-2.5 px-3 font-semibold">Score Range</th>
              <th className="py-2.5 px-3 font-semibold text-right">Sample (N)</th>
              <th className="py-2.5 px-3 font-semibold text-right">Mean Return</th>
              <th className="py-2.5 px-3 font-semibold text-right">Median Return</th>
              <th className="py-2.5 px-3 font-semibold text-right">Win Rate</th>
              <th className="py-2.5 px-3 font-semibold text-right">Annualized</th>
              <th className="py-2.5 px-3 font-semibold text-right">Std Dev</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-subtle)]">
            {deciles.map((d) => {
              const isSmallSample = d.sample_size < minSamplesThreshold;
              const isTopDecile = d.decile >= 8;
              const isBottomDecile = d.decile <= 3;

              return (
                <tr
                  key={`decile-row-${d.decile}`}
                  className="hover:bg-[var(--bg-card)]/40 transition"
                >
                  <td className="py-2.5 px-3 font-bold text-white flex items-center gap-1.5">
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${
                        isTopDecile
                          ? "bg-emerald-400"
                          : isBottomDecile
                          ? "bg-rose-400"
                          : "bg-slate-400"
                      }`}
                    />
                    <span>D{d.decile}</span>
                  </td>
                  <td className="py-2.5 px-3 text-[var(--text-secondary)]">
                    [{d.score_min.toFixed(1)} – {d.score_max.toFixed(1)}]
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <span className="text-white font-semibold">{d.sample_size}</span>
                    {isSmallSample && (
                      <span
                        className="inline-flex items-center ml-1 text-amber-400"
                        title={`Small sample warning: N < ${minSamplesThreshold}`}
                      >
                        <AlertCircle className="w-3 h-3 inline" />
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-right font-bold">
                    <span
                      className={
                        d.mean_forward_return_pct > 0
                          ? "text-emerald-400"
                          : d.mean_forward_return_pct < 0
                          ? "text-rose-400"
                          : "text-[var(--text-dim)]"
                      }
                    >
                      {formatPercent(d.mean_forward_return_pct, { isFraction: false })}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-right text-[var(--text-secondary)]">
                    {formatPercent(d.median_forward_return_pct, { isFraction: false })}
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <span
                      className={
                        d.positive_return_ratio >= 0.55
                          ? "text-emerald-300 font-semibold"
                          : d.positive_return_ratio < 0.45
                          ? "text-rose-300"
                          : "text-[var(--text-secondary)]"
                      }
                    >
                      {(d.positive_return_ratio * 100).toFixed(1)}%
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-right text-[var(--text-secondary)]">
                    {formatPercent(d.annualized_return_pct, { isFraction: false })}
                  </td>
                  <td className="py-2.5 px-3 text-right text-[var(--text-dim)]">
                    {d.std_forward_return_pct.toFixed(2)}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
