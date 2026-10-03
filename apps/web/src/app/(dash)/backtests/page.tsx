"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  FlaskConical,
  Play,
  RotateCcw,
  GitCompare,
  ArrowRight,
  ExternalLink,
  Clock,
  Layers,
  Award,
} from "lucide-react";

import { apiClient } from "@/lib/api/client";
import { formatPrice, formatPercent, formatRelativeTime, formatUTC, EMPTY_FALLBACK } from "@/lib/format";
import { DeltaCell, EmptyState, ErrorState, CardSkeleton } from "@/components/data";
import { BacktestForm } from "@/components/domain/BacktestForm";
import { BacktestJobProgress } from "@/components/domain/BacktestJobProgress";
import { BacktestCompareModal } from "@/components/domain/BacktestCompareModal";

interface BacktestRunSummary {
  id: string;
  strategy_name: string;
  strategy_version: string;
  start_time: string;
  end_time: string;
  parameters: Record<string, any>;
  total_return_pct: number;
  cagr: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_pct: number;
  win_rate: number;
  profit_factor: number;
  benchmark_return_pct: number;
  created_at: string;
}

export default function BacktestsPage() {
  const [runs, setRuns] = useState<BacktestRunSummary[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [compareModalOpen, setCompareModalOpen] = useState(false);

  const fetchRuns = useCallback(async () => {
    setLoadingRuns(true);
    setError(null);
    try {
      const res = await apiClient.GET("/api/v1/backtests", {
        params: { query: { limit: 20, offset: 0 } },
      });
      if (res.data && Array.isArray(res.data)) {
        setRuns(res.data as BacktestRunSummary[]);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load historical backtest runs.");
    } finally {
      setLoadingRuns(false);
    }
  }, []);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  const handleLaunchJob = async (payload: any) => {
    try {
      const res = await apiClient.POST("/api/v1/backtests", {
        body: payload,
      });

      if (res.error) {
        throw new Error((res.error as any)?.detail || "Failed to submit backtest job.");
      }

      if (res.data?.job_id) {
        setActiveJobId(res.data.job_id);
      }
    } catch (err: any) {
      alert(err?.message || "Failed to dispatch backtest job.");
    }
  };

  const toggleSelectRun = (id: string) => {
    if (selectedRunIds.includes(id)) {
      setSelectedRunIds(selectedRunIds.filter((r) => r !== id));
    } else {
      if (selectedRunIds.length >= 4) {
        alert("You can compare up to 4 runs simultaneously.");
        return;
      }
      setSelectedRunIds([...selectedRunIds, id]);
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[var(--border-subtle)] gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              Backtest Lab
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-bold">
              VECTOR &amp; EVENT ENGINE
            </span>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Zod-validated parameters, strict t+1 execution, bootstrap confidence intervals, and regime splits.
          </p>
        </div>

        {selectedRunIds.length >= 2 && (
          <button
            type="button"
            onClick={() => setCompareModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] bg-purple-600 hover:bg-purple-500 text-white text-xs font-mono font-bold transition shadow-lg shadow-purple-600/20"
          >
            <GitCompare className="w-3.5 h-3.5" />
            <span>Compare ({selectedRunIds.length}) Runs</span>
          </button>
        )}
      </div>

      {/* Active Job Progress Widget if running */}
      {activeJobId && (
        <BacktestJobProgress
          jobId={activeJobId}
          onComplete={(result) => {
            fetchRuns();
          }}
          onCancel={() => {
            setActiveJobId(null);
          }}
        />
      )}

      {/* Simulation Form (Never auto-runs on load) */}
      <BacktestForm onSubmit={handleLaunchJob} submitting={Boolean(activeJobId)} />

      {/* Recent Simulation Runs Table */}
      <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 flex flex-col space-y-3">
        <div className="flex items-center justify-between pb-2 border-b border-[var(--border-subtle)]">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-sky-400" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-white">
              Historical Backtest Catalog ({runs.length} runs)
            </h2>
          </div>
          <span className="text-[11px] font-mono text-[var(--text-dim)]">
            Select 2–4 runs to compare
          </span>
        </div>

        {error && (
          <ErrorState
            title="Runs Unavailable"
            message={error}
            onRetry={fetchRuns}
          />
        )}

        {loadingRuns && !error ? (
          <div className="space-y-2 py-4">
            <CardSkeleton />
            <CardSkeleton />
          </div>
        ) : runs.length === 0 ? (
          <EmptyState
            title="No Completed Backtest Runs"
            description="Configure parameters above and click 'Launch Backtest Job' to run your first simulation."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-[var(--bg-card)] text-[10px] uppercase text-[var(--text-dim)] border-b border-[var(--border-subtle)]">
                <tr>
                  <th className="py-2.5 px-3 w-8 text-center">Compare</th>
                  <th className="py-2.5 px-3">Run ID</th>
                  <th className="py-2.5 px-3">Strategy</th>
                  <th className="py-2.5 px-3 text-right">Total Return</th>
                  <th className="py-2.5 px-3 text-right">CAGR</th>
                  <th className="py-2.5 px-3 text-right">Sharpe</th>
                  <th className="py-2.5 px-3 text-right">Max DD</th>
                  <th className="py-2.5 px-3 text-right">Win Rate</th>
                  <th className="py-2.5 px-4 text-center">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)]">
                {runs.map((r) => {
                  const isSelected = selectedRunIds.includes(r.id);
                  return (
                    <tr
                      key={r.id}
                      className={`hover:bg-[var(--bg-card)]/50 transition ${
                        isSelected ? "bg-purple-500/10" : ""
                      }`}
                    >
                      <td className="py-2.5 px-3 text-center">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelectRun(r.id)}
                          className="rounded border-[var(--border-subtle)] text-purple-600 focus:ring-0 cursor-pointer"
                        />
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-[var(--text-secondary)]">
                        #{r.id.slice(0, 8)}
                      </td>
                      <td className="py-2.5 px-3 font-bold text-white">
                        <div>{r.strategy_name}</div>
                        <span className="text-[10px] text-[var(--text-dim)] font-normal">
                          {r.strategy_version}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <DeltaCell value={r.total_return_pct} isFraction={false} />
                      </td>
                      <td className="py-2.5 px-3 text-right text-white">
                        {r.cagr !== null ? `${r.cagr.toFixed(2)}%` : EMPTY_FALLBACK}
                      </td>
                      <td className="py-2.5 px-3 text-right font-bold text-sky-400">
                        {r.sharpe_ratio !== null ? r.sharpe_ratio.toFixed(2) : EMPTY_FALLBACK}
                      </td>
                      <td className="py-2.5 px-3 text-right text-rose-400 font-semibold">
                        {r.max_drawdown_pct !== null
                          ? `-${Math.abs(r.max_drawdown_pct).toFixed(2)}%`
                          : EMPTY_FALLBACK}
                      </td>
                      <td className="py-2.5 px-3 text-right text-white">
                        {r.win_rate !== null ? `${(r.win_rate <= 1 ? r.win_rate * 100 : r.win_rate).toFixed(1)}%` : EMPTY_FALLBACK}
                      </td>
                      <td className="py-2.5 px-4 text-center">
                        <Link
                          href={`/backtests/${r.id}`}
                          className="inline-flex items-center gap-1 text-[11px] text-purple-400 hover:text-purple-300 font-semibold transition"
                        >
                          <span>Analyze</span>
                          <ArrowRight className="w-3.5 h-3.5" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Compare Modal */}
      <BacktestCompareModal
        runIds={selectedRunIds}
        isOpen={compareModalOpen}
        onClose={() => setCompareModalOpen(false)}
      />
    </div>
  );
}
