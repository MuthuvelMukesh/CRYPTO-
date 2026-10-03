"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  Radio,
  LogOut,
  User,
  Activity,
  Globe,
} from "lucide-react";
import { RegimeBadge } from "@/components/domain/RegimeBadge";

interface TopBarProps {
  onOpenCommandPalette?: () => void;
  dataMode?: string;
  regime?: string;
  regimeConfidence?: number;
  sseStatus?: "connected" | "reconnecting" | "offline";
}

export function TopBar({
  onOpenCommandPalette,
  dataMode = "HISTORICAL",
  regime = "NEUTRAL",
  regimeConfidence = 0.85,
  sseStatus = "connected",
}: TopBarProps) {
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await fetch("/api/auth", { method: "DELETE" });
      router.push("/login");
      router.refresh();
    } catch {
      router.push("/login");
    } finally {
      setLoggingOut(false);
    }
  };

  const getModeColor = (mode: string) => {
    switch (mode.toUpperCase()) {
      case "LIVE":
        return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
      case "HISTORICAL":
        return "bg-sky-500/15 text-sky-400 border-sky-500/30";
      case "SYNTHETIC_TEST":
        return "bg-amber-500/15 text-amber-300 border-amber-500/40 animate-pulse";
      case "REPLAY":
        return "bg-purple-500/15 text-purple-300 border-purple-500/30";
      default:
        return "bg-slate-700/30 text-slate-300 border-slate-600";
    }
  };

  const getRegimeColor = (r: string) => {
    const norm = r.toUpperCase();
    if (norm.includes("BULL") || norm.includes("RISK_ON")) {
      return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
    }
    if (norm.includes("BEAR") || norm.includes("RISK_OFF")) {
      return "text-rose-400 bg-rose-500/10 border-rose-500/30";
    }
    return "text-sky-400 bg-sky-500/10 border-sky-500/30";
  };

  return (
    <header className="h-14 border-b border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 flex items-center justify-between z-20 shrink-0">
      {/* Left: Command Search Trigger */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onOpenCommandPalette}
          className="flex items-center gap-2 px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs text-[var(--text-muted)] hover:text-white hover:border-[var(--border-strong)] transition w-56 md:w-64"
        >
          <Search className="w-3.5 h-3.5" />
          <span className="truncate">Search assets, commands...</span>
          <kbd className="ml-auto text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-dim)]">
            Ctrl K
          </kbd>
        </button>

        {/* Exchange pill */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[11px] font-mono text-[var(--text-secondary)]">
          <Globe className="w-3 h-3 text-[var(--text-muted)]" />
          <span>BINANCE</span>
        </div>
      </div>

      {/* Right: Telemetry & State Badges */}
      <div className="flex items-center gap-2.5">
        {/* Regime Badge */}
        <RegimeBadge regime={regime} confidence={regimeConfidence} size="sm" />

        {/* Data Mode Pill (Invariant 3) */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[var(--radius-sm)] border text-[11px] font-bold font-mono tracking-wider ${getModeColor(
            dataMode
          )}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-current" />
          <span>{dataMode.toUpperCase()}</span>
        </div>

        {/* Live SSE Stream Pulse */}
        <div
          className={`hidden md:flex items-center gap-1.5 px-2 py-1 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[10px] font-mono ${
            sseStatus === "connected"
              ? "text-emerald-400"
              : sseStatus === "reconnecting"
              ? "text-amber-400 animate-pulse"
              : "text-rose-400"
          }`}
          title={`SSE telemetry status: ${sseStatus}`}
        >
          <Radio className="w-3 h-3" />
          <span className="uppercase">{sseStatus}</span>
        </div>

        {/* User / Logout */}
        <div className="flex items-center gap-1 pl-2 border-l border-[var(--border-subtle)]">
          <div
            className="w-7 h-7 rounded-full bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center text-indigo-300 text-xs font-mono font-bold"
            title="Active Researcher Session"
          >
            <User className="w-3.5 h-3.5" />
          </div>
          <button
            type="button"
            onClick={handleLogout}
            disabled={loggingOut}
            className="p-1.5 rounded text-[var(--text-muted)] hover:text-rose-400 hover:bg-[var(--bg-card)] transition"
            title="Terminate session"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
