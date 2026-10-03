"use client";

import { formatPercent, EMPTY_FALLBACK } from "../../lib/format";

interface DeltaCellProps {
  value: number | string | null | undefined;
  isFraction?: boolean;
  decimals?: number;
  showArrow?: boolean;
  className?: string;
}

export function DeltaCell({
  value,
  isFraction = false,
  decimals = 2,
  showArrow = true,
  className = "",
}: DeltaCellProps) {
  if (value === null || value === undefined || value === "") {
    return <span className={`font-mono text-[var(--text-dim)] ${className}`}>{EMPTY_FALLBACK}</span>;
  }

  const num = typeof value === "string" ? Number.parseFloat(value) : value;
  if (!Number.isFinite(num)) {
    return <span className={`font-mono text-[var(--text-dim)] ${className}`}>{EMPTY_FALLBACK}</span>;
  }

  const effectiveNum = isFraction ? num * 100 : num;
  const isPositive = effectiveNum > 0.0001;
  const isNegative = effectiveNum < -0.0001;

  let colorClass = "text-[var(--text-muted)]";
  let arrow = "";

  if (isPositive) {
    colorClass = "text-emerald-400";
    arrow = "▲ ";
  } else if (isNegative) {
    colorClass = "text-rose-400";
    arrow = "▼ ";
  }

  const formatted = formatPercent(effectiveNum, { isFraction: false, decimals });

  return (
    <span className={`inline-flex items-center justify-end font-mono tabular-nums text-xs font-medium ${colorClass} ${className}`}>
      {showArrow && arrow && <span className="text-[10px] mr-0.5">{arrow}</span>}
      <span>{formatted}</span>
    </span>
  );
}
