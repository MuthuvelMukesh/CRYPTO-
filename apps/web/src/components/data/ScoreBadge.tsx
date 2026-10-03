"use client";

import { formatScore, EMPTY_FALLBACK } from "../../lib/format";

interface ScoreBadgeProps {
  score: number | null | undefined;
  partialData?: boolean;
  size?: "sm" | "md" | "lg";
  showBar?: boolean;
  className?: string;
}

export function ScoreBadge({
  score,
  partialData = false,
  size = "md",
  showBar = false,
  className = "",
}: ScoreBadgeProps) {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return <span className="font-mono text-xs text-[var(--text-dim)]">{EMPTY_FALLBACK}</span>;
  }

  const num = typeof score === "string" ? Number.parseFloat(score) : score;
  const clamped = Math.max(0, Math.min(100, num));

  // Determine color tier
  let badgeColor = "bg-slate-800/40 text-slate-300 border-slate-700";
  let barColor = "bg-slate-500";
  let ratingLabel = "Neutral";

  if (clamped >= 80) {
    badgeColor = "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
    barColor = "bg-emerald-400";
    ratingLabel = "Strong Opportunity";
  } else if (clamped >= 60) {
    badgeColor = "bg-sky-500/15 text-sky-300 border-sky-500/30";
    barColor = "bg-sky-400";
    ratingLabel = "Moderate Bullish";
  } else if (clamped >= 40) {
    badgeColor = "bg-slate-700/30 text-slate-300 border-slate-600";
    barColor = "bg-slate-400";
    ratingLabel = "Neutral / Sideways";
  } else if (clamped >= 20) {
    badgeColor = "bg-amber-500/15 text-amber-300 border-amber-500/30";
    barColor = "bg-amber-400";
    ratingLabel = "Weak Momentum";
  } else {
    badgeColor = "bg-rose-500/15 text-rose-300 border-rose-500/30";
    barColor = "bg-rose-400";
    ratingLabel = "High Risk / Low Rank";
  }

  const sizeClasses = {
    sm: "px-1.5 py-0.5 text-[10px]",
    md: "px-2 py-0.5 text-xs",
    lg: "px-3 py-1 text-sm font-bold",
  }[size];

  const tooltipText = `Composite Score: ${clamped.toFixed(1)}/100 (${ratingLabel})${
    partialData ? "\n⚠️ Partial Data: Missing inputs dynamically redistributed" : ""
  }`;

  return (
    <div
      className={`inline-flex items-center gap-1.5 ${className}`}
      title={tooltipText}
    >
      <div
        className={`inline-flex items-center gap-1 rounded-[var(--radius-sm)] border font-mono font-semibold tabular-nums ${badgeColor} ${sizeClasses}`}
      >
        <span>{formatScore(clamped)}</span>
        {partialData && (
          <span
            className="text-[9px] px-1 py-0.2 rounded bg-amber-500/20 text-amber-400 font-sans font-bold cursor-help"
            title="Partial Data: some factors missing; weights redistributed"
          >
            P
          </span>
        )}
      </div>

      {showBar && (
        <div className="w-12 h-1.5 bg-[var(--bg-card)] rounded-full overflow-hidden border border-[var(--border-subtle)]">
          <div
            className={`h-full rounded-full transition-all duration-300 ${barColor}`}
            style={{ width: `${clamped}%` }}
          />
        </div>
      )}
    </div>
  );
}
