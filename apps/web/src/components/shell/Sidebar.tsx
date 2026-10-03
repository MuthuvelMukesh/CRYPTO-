"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Search,
  Coins,
  Briefcase,
  FlaskConical,
  Flame,
  PieChart,
  Bell,
  LineChart,
  Server,
  Settings,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useState } from "react";

const NAV_ITEMS = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/scanner", label: "Scanner", icon: Search },
  { href: "/assets/BTC", label: "Asset Deep-Dive", icon: Coins },
  { href: "/portfolio", label: "Paper Portfolio", icon: Briefcase },
  { href: "/backtests", label: "Backtest Lab", icon: FlaskConical },
  { href: "/memes", label: "Meme Radar", icon: Flame },
  { href: "/sectors", label: "Sectors & Rotation", icon: PieChart },
  { href: "/alerts", label: "Alerts Center", icon: Bell },
  { href: "/research", label: "Research & IC", icon: LineChart },
  { href: "/system", label: "System Health", icon: Server },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`h-screen bg-[var(--bg-surface)] border-r border-[var(--border-subtle)] flex flex-col transition-all duration-200 z-30 shrink-0 ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      {/* Brand Header */}
      <div className="h-14 border-b border-[var(--border-subtle)] flex items-center justify-between px-3.5">
        {!collapsed ? (
          <div className="flex items-center gap-2 overflow-hidden">
            <div className="w-7 h-7 rounded-[var(--radius-sm)] bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400 shrink-0">
              <span className="font-black text-xs font-mono">QL</span>
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-bold text-white tracking-wider font-mono">QUANT LAB</span>
              <span className="text-[10px] text-indigo-400 font-semibold tracking-wider">v3.0 PLATFORM</span>
            </div>
          </div>
        ) : (
          <div className="w-8 h-8 mx-auto rounded-[var(--radius-sm)] bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400 font-black text-xs font-mono">
            QL
          </div>
        )}

        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="p-1 rounded text-[var(--text-muted)] hover:text-white hover:bg-[var(--bg-card)] transition"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation List */}
      <nav className="flex-1 py-3 px-2 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive =
            pathname === item.href ||
            (item.href !== "/overview" && pathname.startsWith(item.href));

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-2.5 py-2 rounded-[var(--radius-sm)] text-xs font-medium transition ${
                isActive
                  ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30"
                  : "text-[var(--text-secondary)] hover:text-white hover:bg-[var(--bg-card)]"
              }`}
              title={collapsed ? item.label : undefined}
            >
              <Icon className={`w-4 h-4 shrink-0 ${isActive ? "text-indigo-400" : "text-[var(--text-muted)]"}`} />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Footer Invariant Indicator */}
      <div className="p-3 border-t border-[var(--border-subtle)] bg-[var(--bg-card)]/50">
        {!collapsed ? (
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
            <div className="flex flex-col text-[10px] leading-tight">
              <span className="font-semibold text-emerald-400">PAPER TRADING ONLY</span>
              <span className="text-[var(--text-dim)]">Execution gateway locked</span>
            </div>
          </div>
        ) : (
          <div className="flex justify-center" title="Paper Trading Locked">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
        )}
      </div>
    </aside>
  );
}
