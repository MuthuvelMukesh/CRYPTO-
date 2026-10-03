"use client";

import { Flame, ShieldAlert } from "lucide-react";

export default function MemesPage() {
  return (
    <div className="space-y-4">
      <div className="pb-3 border-b border-[var(--border-subtle)] flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            Meme Radar
            <span className="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono">
              High Risk / High Convexity
            </span>
          </h1>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            DEX liquidity, holder distribution concentration, and rug risk penalties.
          </p>
        </div>

        <div className="flex items-center gap-1.5 px-3 py-1 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-semibold">
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>Strict Penalty Matrix</span>
        </div>
      </div>

      <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center">
        <Flame className="w-8 h-8 text-amber-400 mx-auto mb-2" />
        <h3 className="text-sm font-semibold text-white">Meme Liquidity Radar</h3>
        <p className="text-xs text-[var(--text-muted)] mt-1 max-w-md mx-auto">
          Screening on-chain pools, volume acceleration, and holder top-10 concentration flags.
        </p>
      </div>
    </div>
  );
}
