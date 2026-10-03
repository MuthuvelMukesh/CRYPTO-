"use client";

import { Settings } from "lucide-react";

export default function SettingsPage() {
  return (
    <div className="space-y-4">
      <div className="pb-3 border-b border-[var(--border-subtle)]">
        <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
          Workstation Settings
          <span className="text-xs px-2 py-0.5 rounded bg-slate-700/50 text-slate-300 font-mono">
            Preferences
          </span>
        </h1>
        <p className="text-xs text-[var(--text-muted)] mt-0.5">
          Theme preferences, precision defaults, timezone display, and API key management.
        </p>
      </div>

      <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center">
        <Settings className="w-8 h-8 text-[var(--text-dim)] mx-auto mb-2" />
        <h3 className="text-sm font-semibold text-white">Workstation Configuration</h3>
        <p className="text-xs text-[var(--text-muted)] mt-1 max-w-md mx-auto">
          Manage local display formatting, watchlists, notification destinations, and cache retention.
        </p>
      </div>
    </div>
  );
}
