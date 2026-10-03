"use client";

import { Search, SlidersHorizontal, RefreshCw } from "lucide-react";

export default function ScannerPage() {
  return (
    <div className="space-y-4">
      {/* Page Title & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[var(--border-subtle)]">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            Market Scanner
            <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-mono font-medium">
              Rankings & Factors
            </span>
          </h1>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Cross-sectional momentum, volume acceleration, liquidity, and regime scoring.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs text-[var(--text-secondary)] hover:text-white transition"
          >
            <SlidersHorizontal className="w-3.5 h-3.5 text-[var(--text-muted)]" />
            <span>Filters</span>
          </button>
          <button
            type="button"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Rescan Universe</span>
          </button>
        </div>
      </div>

      {/* Scaffold Placeholder Card for Scanner Table */}
      <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center">
        <Search className="w-8 h-8 text-[var(--text-dim)] mx-auto mb-2" />
        <h3 className="text-sm font-semibold text-white">Scanner Engine Online</h3>
        <p className="text-xs text-[var(--text-muted)] mt-1 max-w-md mx-auto">
          Connected to OpenAPI BFF proxy. Virtualized ranking table, factor waterfall, and live SSE streaming will be wired in Step 3.
        </p>
      </div>
    </div>
  );
}
