"use client";

import React, { useEffect, useState } from "react";
import { X, GitCompare, CheckCircle2, TrendingUp, TrendingDown } from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { formatPercent, formatPrice, EMPTY_FALLBACK } from "@/lib/format";
import { DeltaCell } from "@/components/data";

interface BacktestCompareModalProps {
  runIds: string[];
  isOpen: boolean;
  onClose: () => void;
}

export function BacktestCompareModal({
  runIds,
  isOpen,
  onClose,
}: BacktestCompareModalProps) {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || runIds.length === 0) return;

    async function fetchComparison() {
      setLoading(true);
      setError(null);
      try {
        const idsStr = runIds.join(",");
        const res = await apiClient.GET("/api/v1/backtests/compare", {
          params: { query: { ids: idsStr } },
        });
        if (res.data && (res.data as any).comparison) {
          setData((res.data as any).comparison);
        }
      } catch (err: any) {
        setError(err?.message || "Failed to compare backtests.");
      } finally {
        setLoading(false);
      }
    }

    fetchComparison();
  }, [isOpen, runIds]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-xs">
      <div className="w-full max-w-4xl rounded-[var(--radius-md)] border border-[var(--border-strong)] bg-[var(--bg-surface)] shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border-subtle)] bg-[var(--bg-card)]">
          <div className="flex items-center gap-2">
            <GitCompare className="w-4 h-4 text-purple-400" />
            <h2 className="text-sm font-bold text-white tracking-wide">
              Side-by-Side Backtest Strategy Comparison ({runIds.length} runs)
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded text-[var(--text-muted)] hover:text-white transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 overflow-y-auto">
          {error && (
            <div className="p-3 mb-4 rounded bg-rose-500/20 border border-rose-500/30 text-rose-200 text-xs font-mono">
              {error}
            </div>
          )}

          {loading ? (
            <div className="py-12 text-center text-xs font-mono text-[var(--text-muted)]">
              Loading multi-strategy metric matrices...
            </div>
          ) : data.length === 0 ? (
            <div className="py-12 text-center text-xs font-mono text-[var(--text-dim)]">
              No comparative data returned for the selected backtest runs.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-[var(--border-subtle)] text-[10px] text-[var(--text-dim)] uppercase bg-[var(--bg-card)]">
                    <th className="py-3 px-4 font-semibold">Metric Dimension</th>
                    {data.map((r, i) => (
                      <th key={r.id} className="py-3 px-4 font-bold text-white text-right">
                        <div>Run #{r.id.slice(0, 6)}</div>
                        <span className="text-[10px] text-purple-300 font-normal">
                          {r.strategy_name}
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-subtle)]">
                  <tr>
                    <td className="py-2.5 px-4 font-semibold text-[var(--text-secondary)]">Total Return</td>
                    {data.map((r) => (
                      <td key={r.id} className="py-2.5 px-4 text-right">
                        <DeltaCell value={r.total_return_pct} isFraction={false} />
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-2.5 px-4 font-semibold text-[var(--text-secondary)]">CAGR</td>
                    {data.map((r) => (
                      <td key={r.id} className="py-2.5 px-4 text-right font-bold text-white">
                        {r.cagr !== null ? `${r.cagr.toFixed(2)}%` : EMPTY_FALLBACK}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-2.5 px-4 font-semibold text-[var(--text-secondary)]">Sharpe Ratio</td>
                    {data.map((r) => (
                      <td key={r.id} className="py-2.5 px-4 text-right font-bold text-sky-400">
                        {r.sharpe_ratio !== null ? r.sharpe_ratio.toFixed(2) : EMPTY_FALLBACK}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-2.5 px-4 font-semibold text-[var(--text-secondary)]">Sortino Ratio</td>
                    {data.map((r) => (
                      <td key={r.id} className="py-2.5 px-4 text-right text-white">
                        {r.sortino_ratio !== null ? r.sortino_ratio.toFixed(2) : EMPTY_FALLBACK}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-2.5 px-4 font-semibold text-[var(--text-secondary)]">Max Drawdown</td>
                    {data.map((r) => (
                      <td key={r.id} className="py-2.5 px-4 text-right text-rose-400 font-bold">
                        {r.max_drawdown_pct !== null ? `-${Math.abs(r.max_drawdown_pct).toFixed(2)}%` : EMPTY_FALLBACK}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-2.5 px-4 font-semibold text-[var(--text-secondary)]">Win Rate</td>
                    {data.map((r) => (
                      <td key={r.id} className="py-2.5 px-4 text-right text-white">
                        {r.win_rate !== null ? `${(r.win_rate <= 1 ? r.win_rate * 100 : r.win_rate).toFixed(1)}%` : EMPTY_FALLBACK}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-2.5 px-4 font-semibold text-[var(--text-secondary)]">Profit Factor</td>
                    {data.map((r) => (
                      <td key={r.id} className="py-2.5 px-4 text-right font-bold text-emerald-400">
                        {r.profit_factor !== null ? r.profit_factor.toFixed(2) : EMPTY_FALLBACK}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-[var(--border-subtle)] bg-[var(--bg-card)] flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-xs font-mono text-white hover:border-[var(--border-strong)] transition"
          >
            Close Comparison
          </button>
        </div>
      </div>
    </div>
  );
}
