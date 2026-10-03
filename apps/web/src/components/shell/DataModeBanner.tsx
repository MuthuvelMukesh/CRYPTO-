"use client";

import { AlertTriangle } from "lucide-react";

interface DataModeBannerProps {
  dataMode?: string;
}

export function DataModeBanner({ dataMode = "HISTORICAL" }: DataModeBannerProps) {
  const norm = dataMode.toUpperCase();

  if (norm !== "SYNTHETIC_TEST" && norm !== "REPLAY") {
    return null;
  }

  const isSynthetic = norm === "SYNTHETIC_TEST";

  return (
    <div
      role="alert"
      className={`w-full py-1.5 px-4 text-xs font-semibold flex items-center justify-between border-b ${
        isSynthetic
          ? "bg-amber-950/80 text-amber-200 border-amber-500/40"
          : "bg-purple-950/80 text-purple-200 border-purple-500/40"
      }`}
    >
      <div className="flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
        <span>
          {isSynthetic
            ? "SYNTHETIC TEST DATA ACTIVE — Ground-truth simulation only. Do not base research or capital allocations on these records."
            : "REPLAY SIMULATION MODE — Market state replayed from historical tick sequence."}
        </span>
      </div>
      <div className="text-[11px] font-mono uppercase opacity-75">
        Mode: {norm}
      </div>
    </div>
  );
}
