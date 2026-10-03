"use client";

import { Bell } from "lucide-react";

export default function AlertsPage() {
  return (
    <div className="space-y-4">
      <div className="pb-3 border-b border-[var(--border-subtle)]">
        <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
          Alerts Center
          <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-mono">
            Dispatcher & Rules
          </span>
        </h1>
        <p className="text-xs text-[var(--text-muted)] mt-0.5">
          Signal triggers, threshold breaches, Telegram/Discord routing, and dispatch history.
        </p>
      </div>

      <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center">
        <Bell className="w-8 h-8 text-[var(--text-dim)] mx-auto mb-2" />
        <h3 className="text-sm font-semibold text-white">Alert Dispatch Matrix</h3>
        <p className="text-xs text-[var(--text-muted)] mt-1 max-w-md mx-auto">
          Manage alert triggers, cooldown windows, quiet hours, and test webhook dispatches.
        </p>
      </div>
    </div>
  );
}
