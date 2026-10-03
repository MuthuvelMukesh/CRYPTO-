"use client";

import { AlertTriangle, ShieldCheck, Flame, Droplets, Zap } from "lucide-react";

interface RiskChipProps {
  flag: string;
  className?: string;
}

const FLAG_CONFIG: Record<string, { label: string; icon: typeof AlertTriangle; color: string }> = {
  HIGH_CONCENTRATION: {
    label: "Concentration",
    icon: Flame,
    color: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  },
  LOW_LIQUIDITY: {
    label: "Low Liq",
    icon: Droplets,
    color: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  },
  EXTREME_VOLATILITY: {
    label: "Extreme Vol",
    icon: Zap,
    color: "bg-purple-500/15 text-purple-300 border-purple-500/30",
  },
  DELEVERAGING: {
    label: "Deleveraging",
    icon: AlertTriangle,
    color: "bg-orange-500/15 text-orange-300 border-orange-500/30",
  },
  STALE_FEED: {
    label: "Stale Feed",
    icon: AlertTriangle,
    color: "bg-slate-700/30 text-slate-300 border-slate-600",
  },
  CLEAN: {
    label: "Clean",
    icon: ShieldCheck,
    color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  },
};

export function RiskChip({ flag, className = "" }: RiskChipProps) {
  const norm = flag.toUpperCase().trim();
  const config = FLAG_CONFIG[norm] || {
    label: norm.replace(/_/g, " "),
    icon: AlertTriangle,
    color: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  };

  const Icon = config.icon;

  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium border ${config.color} ${className}`}
      title={`Risk Flag: ${flag}`}
    >
      <Icon className="w-2.5 h-2.5 shrink-0" />
      <span>{config.label}</span>
    </span>
  );
}
