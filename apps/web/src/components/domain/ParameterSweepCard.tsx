"use client";

import React, { useState } from "react";
import {
  Grid3X3,
  Play,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  ShieldCheck,
  Award,
} from "lucide-react";
import { EMPTY_FALLBACK } from "@/lib/format";

interface SweepCell {
  param_x: any;
  param_y: any;
  train_sharpe: number;
  test_sharpe: number;
  train_return_pct: number;
  test_return_pct: number;
  train_max_drawdown_pct: number;
  test_max_drawdown_pct: number;
  efficiency_ratio: number;
  is_overfit: boolean;
}

interface ParameterSweepResponse {
  strategy_name: string;
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
  param_x_name: string;
  param_x_values: any[];
  param_y_name: string;
  param_y_values: any[];
  cells: SweepCell[];
  best_is_params: Record<string, any>;
  best_oos_params: Record<string, any>;
  overfit_warning: boolean;
  data_mode: string;
}

export function ParameterSweepCard() {
  const [strategyName, setStrategyName] = useState("MomentumBreakout");
  const [paramXName, setParamXName] = useState("stop_loss_pct");
  const [paramXValues, setParamXValues] = useState<number[]>([0.05, 0.08, 0.12]);
  const [paramYName, setParamYName] = useState("take_profit_pct");
  const [paramYValues, setParamYValues] = useState<number[]>([0.15, 0.25, 0.35]);
  const [trainRatio, setTrainRatio] = useState(0.7);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ParameterSweepResponse | null>(null);

  const handleRunSweep = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/proxy/api/v1/backtests/sweep", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          strategy_name: strategyName,
          symbols: ["BTC", "ETH", "SOL"],
          train_ratio: trainRatio,
          param_x_name: paramXName,
          param_x_values: paramXValues,
          param_y_name: paramYName,
          param_y_values: paramYValues,
          base_parameters: { top_n_assets: 3 },
        }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail || `Sweep execution failed (${res.status})`);
      }
      const data = await res.json();
      setResult(data);
    } catch (err: any) {
      setError(err?.message || "Failed to execute parameter sweep");
    } finally {
      setLoading(false);
    }
  };

  const getCellColor = (cell: SweepCell) => {
    if (cell.is_overfit) {
      return "bg-rose-500/20 text-rose-300 border-rose-500/40";
    }
    if (cell.test_sharpe >= 1.5) {
      return "bg-emerald-500/25 text-emerald-300 border-emerald-500/40 font-bold";
    }
    if (cell.test_sharpe >= 1.0) {
      return "bg-teal-500/20 text-teal-300 border-teal-500/30";
    }
    if (cell.test_sharpe >= 0.5) {
      return "bg-cyan-500/15 text-cyan-300 border-cyan-500/20";
    }
    if (cell.test_sharpe >= 0.0) {
      return "bg-slate-800/60 text-slate-300 border-slate-700/40";
    }
    return "bg-rose-500/15 text-rose-300 border-rose-500/30";
  };

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[var(--border-subtle)] pb-4">
        <div>
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <Grid3X3 className="w-4 h-4 text-cyan-400" />
            In-Sample / Out-of-Sample Parameter Sweep Heatmap
          </h2>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Test strategy stability and detect curve-fitting by partitioning timeline into training (IS) and validation (OOS).
          </p>
        </div>

        <button
          type="button"
          onClick={handleRunSweep}
          disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs transition disabled:opacity-50 shadow-sm"
        >
          {loading ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Play className="w-3.5 h-3.5 fill-current" />
          )}
          <span>{loading ? "Sweeping Grid..." : "Execute Parameter Sweep"}</span>
        </button>
      </div>

      {/* Grid Configuration Controls */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 p-4 rounded-lg bg-[var(--bg-card)]/40 border border-[var(--border-subtle)] text-xs">
        <div className="space-y-1">
          <label className="text-[11px] font-mono uppercase text-[var(--text-dim)]">
            Strategy
          </label>
          <select
            value={strategyName}
            onChange={(e) => setStrategyName(e.target.value)}
            className="w-full bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded px-2.5 py-1.5 text-white font-mono"
          >
            <option value="MomentumBreakout">MomentumBreakout</option>
            <option value="TrendRegimeFilter">TrendRegimeFilter</option>
            <option value="RelativeStrengthRotation">RelativeStrengthRotation</option>
            <option value="FactorRankModel">FactorRankModel</option>
          </select>
        </div>

        <div className="space-y-1">
          <label className="text-[11px] font-mono uppercase text-[var(--text-dim)]">
            Train/Test Split (IS Ratio)
          </label>
          <select
            value={trainRatio}
            onChange={(e) => setTrainRatio(Number(e.target.value))}
            className="w-full bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded px-2.5 py-1.5 text-white font-mono"
          >
            <option value={0.6}>60% IS / 40% OOS</option>
            <option value={0.7}>70% IS / 30% OOS (Recommended)</option>
            <option value={0.8}>80% IS / 20% OOS</option>
          </select>
        </div>

        <div className="space-y-1">
          <label className="text-[11px] font-mono uppercase text-[var(--text-dim)]">
            Param X: {paramXName}
          </label>
          <div className="text-[11px] font-mono text-cyan-300 py-1.5 px-2 bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded">
            [{paramXValues.join(", ")}]
          </div>
        </div>

        <div className="space-y-1">
          <label className="text-[11px] font-mono uppercase text-[var(--text-dim)]">
            Param Y: {paramYName}
          </label>
          <div className="text-[11px] font-mono text-cyan-300 py-1.5 px-2 bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded">
            [{paramYValues.join(", ")}]
          </div>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Sweep Results Heatmap */}
      {result && (
        <div className="space-y-5 pt-2">
          {/* Overfit Warning Banner */}
          <div
            className={`p-3.5 rounded-lg border flex items-center justify-between text-xs ${
              result.overfit_warning
                ? "bg-amber-500/10 border-amber-500/30 text-amber-300"
                : "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
            }`}
          >
            <div className="flex items-center gap-2.5">
              {result.overfit_warning ? (
                <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
              ) : (
                <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
              )}
              <span>
                {result.overfit_warning
                  ? "Overfitting Warning Detected: Discrepancy observed between In-Sample Sharpe and Out-of-Sample validation."
                  : "Anti-Overfitting Validation Passed: Parameter stability holds out-of-sample across test folds."}
              </span>
            </div>
            <span className="font-mono text-[10px] uppercase px-2 py-0.5 rounded bg-black/30 border border-current">
              {result.data_mode}
            </span>
          </div>

          {/* 2D Grid Table */}
          <div className="overflow-x-auto border border-[var(--border-subtle)] rounded-lg p-3 bg-[var(--bg-card)]/20">
            <div className="text-xs font-semibold text-[var(--text-secondary)] mb-2 flex items-center justify-between">
              <span>
                Validation Matrix ({result.param_x_name} &times; {result.param_y_name})
              </span>
              <span className="text-[10px] text-[var(--text-dim)] font-mono">
                Cell format: Test Sharpe (Train Sharpe)
              </span>
            </div>

            <table className="w-full text-center border-collapse">
              <thead>
                <tr>
                  <th className="p-2 text-left text-xs font-mono text-[var(--text-dim)]">
                    {result.param_x_name} \ {result.param_y_name}
                  </th>
                  {result.param_y_values.map((yVal) => (
                    <th
                      key={String(yVal)}
                      className="p-2 text-xs font-mono font-bold text-white border-b border-[var(--border-subtle)]"
                    >
                      {yVal}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.param_x_values.map((xVal) => (
                  <tr key={String(xVal)} className="border-b border-[var(--border-subtle)]/40">
                    <td className="p-2 text-left font-mono font-bold text-xs text-white">
                      {xVal}
                    </td>
                    {result.param_y_values.map((yVal) => {
                      const cell = result.cells.find(
                        (c) => c.param_x === xVal && c.param_y === yVal
                      );
                      if (!cell) {
                        return <td key={String(yVal)} className="p-2 font-mono text-xs text-slate-500">—</td>;
                      }
                      return (
                        <td key={String(yVal)} className="p-1.5">
                          <div
                            className={`p-2.5 rounded border text-xs font-mono transition-transform hover:scale-105 cursor-pointer ${getCellColor(
                              cell
                            )}`}
                            title={`IS Return: ${cell.train_return_pct}% | OOS Return: ${cell.test_return_pct}% | Efficiency: ${cell.efficiency_ratio.toFixed(2)}`}
                          >
                            <div className="font-bold text-sm">
                              {cell.test_sharpe.toFixed(2)}
                            </div>
                            <div className="text-[10px] opacity-80">
                              ({cell.train_sharpe.toFixed(2)})
                            </div>
                            {cell.is_overfit && (
                              <span className="text-[9px] uppercase px-1 rounded bg-rose-500/30 text-rose-300 font-bold mt-1 block">
                                OVERFIT
                              </span>
                            )}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Best Params Summary */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-3.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)]/40 space-y-1">
              <span className="text-[11px] font-mono uppercase text-[var(--text-dim)] flex items-center gap-1.5">
                <Award className="w-3.5 h-3.5 text-amber-400" />
                Best In-Sample (IS) Parameters
              </span>
              <pre className="text-xs font-mono text-cyan-300 p-2 rounded bg-black/40 overflow-x-auto">
                {JSON.stringify(result.best_is_params, null, 2)}
              </pre>
            </div>

            <div className="p-3.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)]/40 space-y-1">
              <span className="text-[11px] font-mono uppercase text-[var(--text-dim)] flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                Best Out-of-Sample (OOS) Parameters
              </span>
              <pre className="text-xs font-mono text-emerald-300 p-2 rounded bg-black/40 overflow-x-auto">
                {JSON.stringify(result.best_oos_params, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
