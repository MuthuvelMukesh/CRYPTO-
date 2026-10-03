"use client";

import { formatRelativeTime, formatUTC } from "../../lib/format";

interface FreshnessDotProps {
  timestamp: string | Date | null | undefined;
  staleThresholdSeconds?: number;
  showLabel?: boolean;
}

export function FreshnessDot({
  timestamp,
  staleThresholdSeconds = 300, // 5 minutes
  showLabel = false,
}: FreshnessDotProps) {
  if (!timestamp) {
    return (
      <span
        className="inline-flex items-center gap-1.5"
        title="Data freshness unknown / no timestamp"
      >
        <span className="w-2 h-2 rounded-full bg-slate-600" />
        {showLabel && <span className="text-[11px] font-mono text-[var(--text-dim)]">—</span>}
      </span>
    );
  }

  const date = typeof timestamp === "string" ? new Date(timestamp) : timestamp;
  const now = Date.now();
  const ageSeconds = Math.max(0, Math.floor((now - date.getTime()) / 1000));

  let status: "fresh" | "aging" | "stale";
  let dotColor: string;
  let pulseClass = "";

  if (ageSeconds < staleThresholdSeconds) {
    status = "fresh";
    dotColor = "bg-emerald-400";
    pulseClass = "animate-pulse";
  } else if (ageSeconds < staleThresholdSeconds * 2) {
    status = "aging";
    dotColor = "bg-amber-400";
  } else {
    status = "stale";
    dotColor = "bg-rose-400";
  }

  const relativeText = formatRelativeTime(date);
  const utcText = formatUTC(date);
  const titleText = `Data Age: ${relativeText} (${ageSeconds}s ago)\nTimestamp: ${utcText}\nStatus: ${status.toUpperCase()}`;

  return (
    <span
      className="inline-flex items-center gap-1.5 cursor-help"
      title={titleText}
      aria-label={`Freshness: ${status}, ${relativeText}`}
    >
      <span className="relative flex h-2 w-2">
        {status === "fresh" && (
          <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${dotColor} ${pulseClass}`} />
        )}
        <span className={`relative inline-flex rounded-full h-2 w-2 ${dotColor}`} />
      </span>
      {showLabel && (
        <span className="text-[11px] font-mono text-[var(--text-muted)] select-none">
          {relativeText}
        </span>
      )}
    </span>
  );
}
