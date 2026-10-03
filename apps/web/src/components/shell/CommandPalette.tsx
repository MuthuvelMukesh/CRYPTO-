"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  LayoutDashboard,
  Coins,
  Briefcase,
  FlaskConical,
  Flame,
  PieChart,
  Bell,
  LineChart,
  Server,
  X,
} from "lucide-react";

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

const COMMANDS = [
  { label: "Market Scanner", href: "/scanner", icon: Search, group: "Navigation" },
  { label: "Market Overview", href: "/overview", icon: LayoutDashboard, group: "Navigation" },
  { label: "Paper Portfolio", href: "/portfolio", icon: Briefcase, group: "Navigation" },
  { label: "Backtest Lab", href: "/backtests", icon: FlaskConical, group: "Navigation" },
  { label: "Meme Radar", href: "/memes", icon: Flame, group: "Navigation" },
  { label: "Sectors & Rotation", href: "/sectors", icon: PieChart, group: "Navigation" },
  { label: "Alerts Center", href: "/alerts", icon: Bell, group: "Navigation" },
  { label: "Research & Attribution", href: "/research", icon: LineChart, group: "Navigation" },
  { label: "System Health", href: "/system", icon: Server, group: "Navigation" },
  { label: "Bitcoin (BTC)", href: "/assets/BTC", icon: Coins, group: "Assets" },
  { label: "Ethereum (ETH)", href: "/assets/ETH", icon: Coins, group: "Assets" },
  { label: "Solana (SOL)", href: "/assets/SOL", icon: Coins, group: "Assets" },
];

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (open) onClose();
        else onClose(); // parent toggles
      }
      if (e.key === "Escape" && open) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const filtered = COMMANDS.filter((cmd) =>
    cmd.label.toLowerCase().includes(query.toLowerCase())
  );

  const handleSelect = (href: string) => {
    onClose();
    router.push(href);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-start justify-center pt-20 p-4">
      <div className="w-full max-w-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-[var(--radius-lg)] shadow-2xl overflow-hidden flex flex-col">
        {/* Search Input */}
        <div className="flex items-center px-4 border-b border-[var(--border-subtle)]">
          <Search className="w-4 h-4 text-[var(--text-muted)] shrink-0" />
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command or jump to asset (BTC, ETH, SOL)..."
            className="w-full bg-transparent px-3 py-3 text-sm text-white placeholder-[var(--text-dim)] focus:outline-none"
          />
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded text-[var(--text-muted)] hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filtered.length === 0 ? (
            <div className="py-6 text-center text-xs text-[var(--text-dim)]">
              No matching pages or assets found.
            </div>
          ) : (
            filtered.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.href}
                  type="button"
                  onClick={() => handleSelect(item.href)}
                  className="w-full flex items-center justify-between px-3 py-2 rounded-[var(--radius-sm)] text-xs text-left text-[var(--text-secondary)] hover:bg-[var(--bg-card)] hover:text-white transition"
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className="w-4 h-4 text-indigo-400" />
                    <span>{item.label}</span>
                  </div>
                  <span className="text-[10px] font-mono uppercase text-[var(--text-dim)]">
                    {item.group}
                  </span>
                </button>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="px-3 py-2 border-t border-[var(--border-subtle)] bg-[var(--bg-card)]/40 flex items-center justify-between text-[10px] text-[var(--text-dim)] font-mono">
          <span>Navigate with click or arrow keys</span>
          <span>Esc to exit</span>
        </div>
      </div>
    </div>
  );
}
