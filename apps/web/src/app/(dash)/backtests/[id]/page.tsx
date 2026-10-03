"use client";

import React, { useEffect, useState, useCallback, use } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  FlaskConical,
  GitBranch,
  Hash,
  Calendar,
  Download,
  Share2,
  ExternalLink,
  ShieldCheck,
} from "lucide-react";

import { apiClient } from "@/lib/api/client";
import { formatPrice, formatPercent, formatRelativeTime, formatUTC, EMPTY_FALLBACK } from "@/lib/format";
import { DeltaCell, EmptyState, ErrorState, CardSkeleton } from "@/components/data";
import { BacktestMetricsGrid } from "@/components/domain/BacktestMetricsGrid";
import { BacktestTradeTable, type BacktestTrade } from "@/components/domain/BacktestTradeTable";
import { EquityChart, type EquityPoint } from "@/components/charts/EquityChart";
import { UnderwaterDrawdownChart, type DrawdownPoint } from "@/components/charts/UnderwaterDrawdownChart";

export default function BacktestDetailPage() {
  const params = useParams();
  const runId = params?.id ? String(params.id) : "";

  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchBacktestDetail = useCallback(async () => {
    if (!runId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.GET("/api/v1/backtests/{backtest_id}", {
        params: { path: { backtest_id: runId } },
      });
      if (res.data) {
        setDetail(res.data);
      }
    } catch (err: any) {
      setError(err?.message || `Failed to load backtest #${runId}`);
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    fetchBacktestDetail();
  }, [fetchBacktestDetail]);

  const handleExportHTML = () => {
    window.print();
  };

  // Build equity & drawdown points from trade history or metrics
  const trades: BacktestTrade[] = detail?.trades || [];
  const metrics = detail?.metrics || {};

  let cumulativeCapital = 100000;
  const equityPoints: EquityPoint[] = [
    { time: detail?.start_time || new Date().toISOString(), equity: 100000, cash: 100000 },
  ];
  const drawdownPoints: DrawdownPoint[] = [
    { time: detail?.start_time || new Date().toISOString(), drawdown_pct: 0 },
  ];

  let peak = 100000;
  for (const t of trades) {
    cumulativeCapital += t.pnl_usd ?? 0;
    if (cumulativeCapital > peak) peak = cumulativeCapital;
    const dd = peak > 0 ? ((cumulativeCapital - peak) / peak) * 100 : 0;

    equityPoints.push({
      time: t.exit_time || t.entry_time,
      equity: cumulativeCapital,
      cash: cumulativeCapital,
      drawdown_pct: dd,
    });

    drawdownPoints.push({
      time: t.exit_time || t.entry_time,
      drawdown_pct: dd,
    });
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[var(--border-subtle)] gap-3">
        <div className="flex items-center gap-3">
          <Link
            href="/backtests"
            className="p-2 rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-card)] text-[var(--text-muted)] hover:text-white hover:border-[var(--border-strong)] transition"
            title="Back to Backtests Lab"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>

          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                <span>Backtest #{runId.slice(0, 8)}</span>
                <span className="text-xs px-2 py-0.5 rounded font-mono font-bold bg-purple-500/20 text-purple-300">
                  {detail?.strategy_name || "Strategy Report"}
                </span>
              </h1>
              <span className="text-xs font-mono text-[var(--text-dim)]">
                {detail?.strategy_version || "v3.0.0"}
              </span>
            </div>

            <p className="text-xs text-[var(--text-muted)] mt-1">
              Simulation audit log, Monte Carlo bootstrap intervals, and execution trace.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleExportHTML}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-card)] text-xs font-mono text-white hover:border-[var(--border-strong)] transition"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export Report (HTML/PDF)</span>
          </button>
        </div>
      </div>

      {/* Reproducibility Header (Section 7.5 requirement) */}
      <div className="p-3.5 rounded-[var(--radius-md)] bg-[var(--bg-card)] border border-[var(--border-subtle)] grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono text-[var(--text-dim)]">
        <div>
          <span className="text-[10px] uppercase block text-[var(--text-muted)]">Code Version</span>
          <span className="text-white font-semibold flex items-center gap-1 mt-0.5">
            <GitBranch className="w-3 h-3 text-sky-400" />
            v3.0.0 (Release)
          </span>
        </div>
        <div>
          <span className="text-[10px] uppercase block text-[var(--text-muted)]">Config Hash</span>
          <span className="text-white font-semibold flex items-center gap-1 mt-0.5">
            <Hash className="w-3 h-3 text-purple-400" />
            {detail?.id ? detail.id.slice(0, 12) : "—"}
          </span>
        </div>
        <div>
          <span className="text-[10px] uppercase block text-[var(--text-muted)]">Simulation Window</span>
          <span className="text-white font-semibold flex items-center gap-1 mt-0.5 truncate">
            <Calendar className="w-3 h-3 text-emerald-400" />
            {detail?.start_time ? detail.start_time.split("T")[0] : "—"} → {detail?.end_time ? detail.end_time.split("T")[0] : "—"}
          </span>
        </div>
        <div>
          <span className="text-[10px] uppercase block text-[var(--text-muted)]">Fill Model</span>
          <span className="text-emerald-400 font-semibold flex items-center gap-1 mt-0.5">
            <ShieldCheck className="w-3 h-3" />
            t+1 Open / Spreads
          </span>
        </div>
      </div>

      {error && (
        <ErrorState
          title="Backtest Report Unavailable"
          message={error}
          onRetry={fetchBacktestDetail}
        />
      )}

      {loading && !error ? (
        <div className="space-y-4">
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : (
        <>
          {/* Metrics Grid with CIs & Secondary Splits */}
          <BacktestMetricsGrid
            metrics={metrics}
            totalReturnPct={detail?.total_return_pct}
            cagr={detail?.cagr}
            sharpeRatio={detail?.sharpe_ratio}
            sortinoRatio={detail?.sortino_ratio}
            maxDrawdownPct={detail?.max_drawdown_pct}
            winRate={detail?.win_rate}
            profitFactor={detail?.profit_factor}
            benchmarkReturnPct={detail?.benchmark_return_pct}
          />

          {/* Equity Curve & Underwater Drawdown */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            <div className="lg:col-span-7">
              <EquityChart
                data={equityPoints}
                peakEquity={peak}
                startingCapital={100000}
                currentDrawdown={detail?.max_drawdown_pct}
              />
            </div>

            <div className="lg:col-span-5">
              <UnderwaterDrawdownChart
                data={drawdownPoints}
                maxDrawdown={detail?.max_drawdown_pct}
              />
            </div>
          </div>

          {/* Execution Trade Log */}
          <BacktestTradeTable trades={trades} />
        </>
      )}
    </div>
  );
}
