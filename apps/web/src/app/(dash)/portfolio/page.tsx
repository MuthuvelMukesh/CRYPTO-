"use client";

import { Briefcase, ShieldCheck } from "lucide-react";

export default function PortfolioPage() {
  return (
    <div className="space-y-4">
      <div className="pb-3 border-b border-[var(--border-subtle)] flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            Paper Portfolio
            <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">
              Live Paper Broker
            </span>
          </h1>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Real-time equity curve, positions, order ticket preview, and reconciled audit ledger.
          </p>
        </div>

        <div className="flex items-center gap-1.5 px-3 py-1 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-semibold">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Ledger Reconciled</span>
        </div>
      </div>

      <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center">
        <Briefcase className="w-8 h-8 text-[var(--text-dim)] mx-auto mb-2" />
        <h3 className="text-sm font-semibold text-white">Paper Broker Accounting</h3>
        <p className="text-xs text-[var(--text-muted)] mt-1 max-w-md mx-auto">
          Multi-asset paper accounts with Decimal precision, order staging, and risk guardrails.
        </p>
      </div>
    </div>
  );
}
