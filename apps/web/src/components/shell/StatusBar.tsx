"use client";

import { Clock, ShieldAlert, Cpu } from "lucide-react";
import { formatRelativeTime } from "@/lib/format";

interface StatusBarProps {
  lastScanTimestamp?: string | null;
  ingestionLagMs?: number | null;
  activeUniverseCount?: number;
}

export function StatusBar({
  lastScanTimestamp = null,
  ingestionLagMs = null,
  activeUniverseCount = 50,
}: StatusBarProps) {
  return (
    <footer className="h-8 border-t border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 flex items-center justify-between text-[11px] text-[var(--text-muted)] z-20 shrink-0 select-none">
      {/* Left: Scan & Ingestion Telemetry */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5" title="Last scanner snapshot execution">
          <Clock className="w-3 h-3 text-[var(--text-dim)]" />
          <span>Scan:</span>
          <span className="font-mono text-[var(--text-secondary)]">
            {lastScanTimestamp ? formatRelativeTime(lastScanTimestamp) : "live syncing"}
          </span>
        </div>

        <div className="hidden sm:flex items-center gap-1.5" title="Ingestion pipeline delay">
          <Cpu className="w-3 h-3 text-[var(--text-dim)]" />
          <span>Ingest Lag:</span>
          <span className="font-mono text-[var(--text-secondary)]">
            {ingestionLagMs !== null ? `${ingestionLagMs}ms` : "< 250ms"}
          </span>
        </div>

        <div className="hidden md:flex items-center gap-1.5">
          <span>Universe:</span>
          <span className="font-mono text-indigo-400 font-semibold">{activeUniverseCount} Assets</span>
        </div>
      </div>

      {/* Right: Mandatory Legal & Paper Guard */}
      <div className="flex items-center gap-1.5 text-amber-400/90 font-medium">
        <ShieldAlert className="w-3 h-3 text-amber-400 shrink-0" />
        <span>Research and paper trading only. Not financial advice.</span>
      </div>
    </footer>
  );
}
