"use client";

import { LineChart } from "lucide-react";

export default function ResearchPage() {
  return (
    <div className="space-y-4">
      <div className="pb-3 border-b border-[var(--border-subtle)]">
        <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
          Research & Attribution
          <span className="text-xs px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 font-mono">
            Phase 6 Validity
          </span>
        </h1>
        <p className="text-xs text-[var(--text-muted)] mt-0.5">
          Factor Information Coefficient (IC) time-series, decile forward returns, and Deflated Sharpe Ratios.
        </p>
      </div>

      <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center">
        <LineChart className="w-8 h-8 text-[var(--text-dim)] mx-auto mb-2" />
        <h3 className="text-sm font-semibold text-white">Attribution Engine</h3>
        <p className="text-xs text-[var(--text-muted)] mt-1 max-w-md mx-auto">
          Connected to /api/v1/research REST endpoints. Decile tables, rolling IC series, and production gate audits.
        </p>
      </div>
    </div>
  );
}
