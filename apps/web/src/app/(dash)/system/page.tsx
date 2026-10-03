"use client";

import { Server, ShieldCheck } from "lucide-react";

export default function SystemPage() {
  return (
    <div className="space-y-4">
      <div className="pb-3 border-b border-[var(--border-subtle)] flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            System & Operations
            <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">
              Infrastructure
            </span>
          </h1>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Component versions, database hypertables, ingestion circuit breakers, and ledger health.
          </p>
        </div>

        <div className="flex items-center gap-1.5 px-3 py-1 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-semibold">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>All Nodes Healthy</span>
        </div>
      </div>

      <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center">
        <Server className="w-8 h-8 text-[var(--text-dim)] mx-auto mb-2" />
        <h3 className="text-sm font-semibold text-white">Platform Health Console</h3>
        <p className="text-xs text-[var(--text-muted)] mt-1 max-w-md mx-auto">
          Displaying /health, /health/versions, database replication, Timescale compression, and worker heartbeats.
        </p>
      </div>
    </div>
  );
}
