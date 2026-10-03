"use client";

import { FlaskConical } from "lucide-react";

export default function BacktestsPage() {
  return (
    <div className="space-y-4">
      <div className="pb-3 border-b border-[var(--border-subtle)] flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            Backtest Lab
            <span className="text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-mono">
              Vector & Event Engine
            </span>
          </h1>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Strict t+1 fills, slippage, pluggable position sizing, and regime performance splits.
          </p>
        </div>
      </div>

      <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center">
        <FlaskConical className="w-8 h-8 text-[var(--text-dim)] mx-auto mb-2" />
        <h3 className="text-sm font-semibold text-white">Backtest Experiment Station</h3>
        <p className="text-xs text-[var(--text-muted)] mt-1 max-w-md mx-auto">
          Asynchronous backtesting jobs, equity vs benchmark curves, cost-stress test, and deflated Sharpe ratios.
        </p>
      </div>
    </div>
  );
}
