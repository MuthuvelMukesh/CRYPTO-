"use client";

import { PieChart } from "lucide-react";

export default function SectorsPage() {
  return (
    <div className="space-y-4">
      <div className="pb-3 border-b border-[var(--border-subtle)]">
        <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
          Sectors & Rotation
          <span className="text-xs px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 font-mono">
            Capital Flows
          </span>
        </h1>
        <p className="text-xs text-[var(--text-muted)] mt-0.5">
          Sector momentum, relative strength vs BTC, and cross-sector rotation matrices.
        </p>
      </div>

      <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center">
        <PieChart className="w-8 h-8 text-[var(--text-dim)] mx-auto mb-2" />
        <h3 className="text-sm font-semibold text-white">Sector Rotation Graph</h3>
        <p className="text-xs text-[var(--text-muted)] mt-1 max-w-md mx-auto">
          Tracking Layer 1, DeFi, AI, Meme, and Infrastructure capital rotation cycles.
        </p>
      </div>
    </div>
  );
}
