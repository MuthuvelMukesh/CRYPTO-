"use client";

import { AlertCircle, RotateCcw } from "lucide-react";

interface ProblemDetails {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
}

interface ErrorStateProps {
  title?: string;
  message?: string;
  problem?: ProblemDetails | null;
  onRetry?: () => void;
  retrying?: boolean;
  className?: string;
}

export function ErrorState({
  title = "Telemetry Feed Error",
  message,
  problem,
  onRetry,
  retrying = false,
  className = "",
}: ErrorStateProps) {
  const displayTitle = problem?.title || title;
  const displayDetail =
    problem?.detail ||
    message ||
    "An unexpected error occurred while communicating with the quantitative backend service.";
  const statusCode = problem?.status;

  return (
    <div
      role="alert"
      className={`rounded-[var(--radius-md)] border border-rose-500/30 bg-rose-950/20 p-6 text-center flex flex-col items-center justify-center max-w-lg mx-auto my-6 ${className}`}
    >
      <div className="w-11 h-11 rounded-full bg-rose-500/10 border border-rose-500/25 flex items-center justify-center text-rose-400 mb-3">
        <AlertCircle className="w-5 h-5" />
      </div>

      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-rose-200">{displayTitle}</h3>
        {statusCode && (
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 font-bold">
            HTTP {statusCode}
          </span>
        )}
      </div>

      <p className="text-xs text-rose-300/80 mt-1.5 leading-relaxed max-w-md font-mono">
        {displayDetail}
      </p>

      {problem?.type && (
        <span className="text-[10px] text-rose-400/60 mt-1 truncate max-w-sm">
          Type: {problem.type}
        </span>
      )}

      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          disabled={retrying}
          className="mt-4 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-rose-500/40 text-xs font-semibold text-rose-200 hover:bg-rose-900/30 hover:text-white disabled:opacity-50 transition"
        >
          <RotateCcw className={`w-3.5 h-3.5 ${retrying ? "animate-spin" : ""}`} />
          <span>{retrying ? "Retrying..." : "Retry Request"}</span>
        </button>
      )}
    </div>
  );
}
