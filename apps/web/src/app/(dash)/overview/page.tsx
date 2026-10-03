"use client";

import { Activity } from "lucide-react";

export default function OverviewPage() {
  return (
    <div className="space-y-4">
      <div className="pb-3 border-b border-[var(--border-subtle)]">
        <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
          Market Overview
          <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">
            Macro & Regimes
          </span>
        </h1>
        <p className="text-xs text-[var(--text-muted)] mt-0.5">
          Macro state, breadth, top performers, and sector heatmap.
        </p>
      </div>

      <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center">
        <Activity className="w-8 h-8 text-[var(--text-dim)] mx-auto mb-2" />
        <h3 className="text-sm font-semibold text-white">Overview Terminal</h3>
        <p className="text-xs text-[var(--text-muted)] mt-1 max-w-md mx-auto">
          Regime telemetry and breadth indices wired to FastAPI endpoints.
        </p>
      </div>
    </div>
  );
}
