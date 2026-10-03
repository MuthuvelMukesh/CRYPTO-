"use client";

import React, { useState, useEffect } from "react";
import {
  TrendingUp,
  BarChart3,
  Layers,
  FlaskConical,
  AlertTriangle,
  FileCheck2,
  RefreshCw,
  Info,
} from "lucide-react";
import { formatPercent, formatNumber, EMPTY_FALLBACK } from "@/lib/format";
import { RollingICChart, RollingICPoint } from "@/components/charts/RollingICChart";
import { DecileBarChart } from "@/components/charts/DecileBarChart";
import { DecileTable, DecileRow } from "@/components/domain/DecileTable";
import { ModelGateAuditCard } from "@/components/domain/ModelGateAuditCard";

interface AttributionData {
  horizon: string;
  sample_size: number;
  data_mode: string;
  pearson_ic: number;
  pearson_p_value: number;
  pearson_ci_lower: number;
  pearson_ci_upper: number;
  spearman_rank_ic: number;
  spearman_p_value: number;
  spearman_ci_lower: number;
  spearman_ci_upper: number;
  hit_rate_pct: number;
  hit_rate_ci_lower: number;
  hit_rate_ci_upper: number;
  deciles: DecileRow[];
  monotonicity_spread_pct: number;
  small_sample_warning: boolean;
  small_sample_message: string | null;
  plain_language_summary: string;
}

interface TrialsData {
  total_trials: number;
  variance_trials: number;
  mean_sharpe: number;
  expected_max_sharpe: number;
}

export default function ResearchPage() {
  const [horizon, setHorizon] = useState<"1d" | "7d" | "30d">("1d");
  const [useSynthetic, setUseSynthetic] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(true);
  const [attribution, setAttribution] = useState<AttributionData | null>(null);
  const [icPoints, setIcPoints] = useState<RollingICPoint[]>([]);
  const [trials, setTrials] = useState<TrialsData | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      // 1. Fetch Attribution Report
      const attrRes = await fetch(
        `/api/proxy/api/v1/research/attribution?horizon=${horizon}&synthetic=${useSynthetic}`
      );
      if (attrRes.ok) {
        const data = await attrRes.json();
        setAttribution(data);
      }

      // 2. Fetch Rolling IC series
      const icRes = await fetch(
        `/api/proxy/api/v1/research/ic?horizon=${horizon}&synthetic=${useSynthetic}`
      );
      if (icRes.ok) {
        const data = await icRes.json();
        setIcPoints(data.points || []);
      }

      // 3. Fetch Trials Tracker statistics
      const trialsRes = await fetch("/api/proxy/api/v1/research/trials");
      if (trialsRes.ok) {
        const data = await trialsRes.json();
        setTrials(data);
      }
    } catch {
      // Handled via state
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [horizon, useSynthetic]);

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="pb-4 border-b border-[var(--border-subtle)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              Quantitative Research & Factor Attribution
            </h1>
            <span
              className={`text-xs px-2 py-0.5 rounded font-mono font-medium ${
                attribution?.data_mode === "SYNTHETIC_TEST"
                  ? "bg-amber-500/10 text-amber-300 border border-amber-500/20"
                  : "bg-sky-500/10 text-sky-300 border border-sky-500/20"
              }`}
            >
              Mode: {attribution?.data_mode || "HISTORICAL"}
            </span>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Information Coefficient (IC) time-series, decile forward returns, and Deflated Sharpe Ratio multiple-testing controls.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* Horizon Switcher */}
          <div className="flex items-center bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-[var(--radius-sm)] p-0.5 text-xs font-mono">
            {(["1d", "7d", "30d"] as const).map((h) => (
              <button
                key={h}
                onClick={() => setHorizon(h)}
                className={`px-3 py-1 rounded-[var(--radius-sm)] transition ${
                  horizon === h
                    ? "bg-[var(--bg-card)] text-white font-bold shadow-sm"
                    : "text-[var(--text-dim)] hover:text-white"
                }`}
              >
                {h.toUpperCase()}
              </button>
            ))}
          </div>

          {/* Mode Switcher */}
          <button
            onClick={() => setUseSynthetic(!useSynthetic)}
            className={`px-3 py-1.5 rounded-[var(--radius-sm)] text-xs font-mono border transition flex items-center gap-1.5 ${
              useSynthetic
                ? "bg-amber-500/10 border-amber-500/30 text-amber-300 hover:bg-amber-500/20"
                : "bg-[var(--bg-surface)] border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-white"
            }`}
            title="Toggle between real historical database snapshots and synthetic benchmark dataset"
          >
            <FlaskConical className="w-3.5 h-3.5" />
            <span>{useSynthetic ? "Synthetic Benchmark" : "Historical DB"}</span>
          </button>

          {/* Refresh */}
          <button
            onClick={fetchData}
            disabled={loading}
            className="p-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-dim)] hover:text-white transition disabled:opacity-50"
            title="Refresh attribution metrics"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Small Sample Warning Alert */}
      {attribution?.small_sample_warning && (
        <div className="rounded-[var(--radius-sm)] border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-300 flex items-start gap-2.5">
          <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" />
          <div>
            <span className="font-bold">Small Sample Warning: </span>
            <span>
              {attribution.small_sample_message ||
                `Sample size (N=${attribution.sample_size}) is below threshold (N=30). Statistical estimators exhibit elevated variance.`}
            </span>
          </div>
        </div>
      )}

      {/* Top Statistical Metrics Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-xs font-mono">
        {/* Pearson IC */}
        <div className="rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3.5">
          <div className="flex items-center justify-between text-[10px] uppercase text-[var(--text-dim)] mb-1">
            <span>Pearson IC (Linear)</span>
            <span className="text-white/60">p: {attribution ? attribution.pearson_p_value.toFixed(3) : EMPTY_FALLBACK}</span>
          </div>
          <div className="text-xl font-extrabold text-white">
            {attribution ? (
              <span className={attribution.pearson_ic > 0 ? "text-emerald-400" : attribution.pearson_ic < 0 ? "text-rose-400" : "text-white"}>
                {attribution.pearson_ic > 0 ? "+" : ""}
                {attribution.pearson_ic.toFixed(3)}
              </span>
            ) : (
              EMPTY_FALLBACK
            )}
          </div>
          <span className="text-[10px] text-sky-400 mt-1 block">
            95% CI: [
            {attribution ? attribution.pearson_ci_lower.toFixed(3) : EMPTY_FALLBACK},{" "}
            {attribution ? attribution.pearson_ci_upper.toFixed(3) : EMPTY_FALLBACK}]
          </span>
        </div>

        {/* Spearman Rank IC */}
        <div className="rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3.5">
          <div className="flex items-center justify-between text-[10px] uppercase text-[var(--text-dim)] mb-1">
            <span>Spearman IC (Rank)</span>
            <span className="text-white/60">p: {attribution ? attribution.spearman_p_value.toFixed(3) : EMPTY_FALLBACK}</span>
          </div>
          <div className="text-xl font-extrabold text-white">
            {attribution ? (
              <span className={attribution.spearman_rank_ic > 0 ? "text-emerald-400" : attribution.spearman_rank_ic < 0 ? "text-rose-400" : "text-white"}>
                {attribution.spearman_rank_ic > 0 ? "+" : ""}
                {attribution.spearman_rank_ic.toFixed(3)}
              </span>
            ) : (
              EMPTY_FALLBACK
            )}
          </div>
          <span className="text-[10px] text-emerald-400 mt-1 block">
            95% CI: [
            {attribution ? attribution.spearman_ci_lower.toFixed(3) : EMPTY_FALLBACK},{" "}
            {attribution ? attribution.spearman_ci_upper.toFixed(3) : EMPTY_FALLBACK}]
          </span>
        </div>

        {/* Directional Hit Rate */}
        <div className="rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3.5">
          <span className="text-[10px] uppercase text-[var(--text-dim)] block mb-1">
            Directional Hit Rate (Score &gt; 50)
          </span>
          <div className="text-xl font-extrabold text-white">
            {attribution ? (
              <span className={attribution.hit_rate_pct >= 52 ? "text-emerald-400" : "text-white"}>
                {attribution.hit_rate_pct.toFixed(1)}%
              </span>
            ) : (
              EMPTY_FALLBACK
            )}
          </div>
          <span className="text-[10px] text-[var(--text-dim)] mt-1 block">
            95% CI: [
            {attribution ? attribution.hit_rate_ci_lower.toFixed(1) : EMPTY_FALLBACK}%,{" "}
            {attribution ? attribution.hit_rate_ci_upper.toFixed(1) : EMPTY_FALLBACK}%]
          </span>
        </div>

        {/* Multiple Testing Trials & Expected Max Sharpe */}
        <div className="rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3.5">
          <div className="flex items-center justify-between text-[10px] uppercase text-[var(--text-dim)] mb-1">
            <span>Multiple Testing</span>
            <span className="text-indigo-400 font-bold">N={trials?.total_trials || 1} Trials</span>
          </div>
          <div className="text-xl font-extrabold text-white">
            {trials ? (
              <span>E[Max SR]: {trials.expected_max_sharpe.toFixed(2)}</span>
            ) : (
              EMPTY_FALLBACK
            )}
          </div>
          <span className="text-[10px] text-indigo-300/80 mt-1 block">
            Deflated Sharpe Haircut Guard
          </span>
        </div>
      </div>

      {/* Rolling IC Time-Series Chart */}
      <RollingICChart points={icPoints} horizon={horizon} />

      {/* Decile Forward Returns Grid */}
      <div className="space-y-4">
        <DecileBarChart
          deciles={attribution?.deciles}
          monotonicitySpreadPct={attribution?.monotonicity_spread_pct}
          horizon={horizon}
        />

        <DecileTable
          deciles={attribution?.deciles}
          minSamplesThreshold={30}
        />
      </div>

      {/* Institutional Explainer & Production Gate Audit */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Plain Language Factor Explainer */}
        <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 pb-2 mb-3 border-b border-[var(--border-subtle)]">
              <Info className="w-4 h-4 text-sky-400" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
                Factor Attribution Plain-Language Audit
              </h3>
            </div>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              {attribution?.plain_language_summary ||
                "Awaiting quantitative factor evaluation from the backend analytics engine."}
            </p>

            <div className="mt-4 p-3 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[11px] font-mono space-y-1.5 text-[var(--text-muted)]">
              <div className="flex items-center justify-between">
                <span>Evaluated Observation Pairs:</span>
                <span className="text-white font-bold">{attribution?.sample_size || 0}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>D10 – D1 Monotonicity Spread:</span>
                <span
                  className={`font-bold ${
                    (attribution?.monotonicity_spread_pct || 0) > 0
                      ? "text-emerald-400"
                      : "text-rose-400"
                  }`}
                >
                  {formatPercent(attribution?.monotonicity_spread_pct, { isFraction: false })}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>Statistical Significance (p &lt; 0.05):</span>
                <span
                  className={`font-bold ${
                    (attribution?.pearson_p_value || 1) < 0.05
                      ? "text-emerald-400"
                      : "text-amber-400"
                  }`}
                >
                  {(attribution?.pearson_p_value || 1) < 0.05 ? "YES (REJECT H0)" : "NO (FAIL TO REJECT)"}
                </span>
              </div>
            </div>
          </div>

          <div className="pt-3 mt-3 border-t border-[var(--border-subtle)] text-[10px] text-[var(--text-dim)] font-mono">
            Platform Rule: Strategies with non-monotonic decile spreads are flagged during portfolio optimization.
          </div>
        </div>

        {/* ML Production Gate Audit */}
        <ModelGateAuditCard />
      </div>
    </div>
  );
}
