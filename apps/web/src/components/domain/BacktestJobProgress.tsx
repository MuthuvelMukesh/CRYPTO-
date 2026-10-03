"use client";

import React, { useEffect, useState } from "react";
import {
  RotateCcw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  StopCircle,
  ArrowRight,
  GitBranch,
  Hash,
} from "lucide-react";
import Link from "next/link";
import { apiClient } from "@/lib/api/client";

interface BacktestJobProgressProps {
  jobId: string;
  onComplete?: (result: any) => void;
  onCancel?: () => void;
  className?: string;
}

export function BacktestJobProgress({
  jobId,
  onComplete,
  onCancel,
  className = "",
}: BacktestJobProgressProps) {
  const [job, setJob] = useState<any>(null);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let interval: any = null;
    let isMounted = true;

    async function pollJob() {
      try {
        const { data, error } = await apiClient.GET(
          "/api/v1/backtests/jobs/{job_id}" as any,
          {
            params: { path: { job_id: jobId } },
          }
        );

        if (error) {
          throw new Error((error as any)?.detail || "Job polling error");
        }

        if (isMounted && data) {
          setJob(data);

          if (data.status === "COMPLETED") {
            clearInterval(interval);
            onComplete?.(data);
          } else if (data.status === "FAILED" || data.status === "CANCELLED") {
            clearInterval(interval);
          }
        }
      } catch (err: any) {
        if (isMounted) setError(err?.message || "Failed to poll job status");
      }
    }

    pollJob();
    interval = setInterval(pollJob, 1000);

    return () => {
      isMounted = false;
      if (interval) clearInterval(interval);
    };
  }, [jobId, onComplete]);

  const handleCancel = async () => {
    setCancelling(true);
    try {
      const { data, error } = await apiClient.POST(
        "/api/v1/backtests/jobs/{job_id}/cancel" as any,
        {
          params: { path: { job_id: jobId } },
        }
      );
      if (error) throw new Error((error as any)?.detail || "Cancel failed");
      onCancel?.();
    } catch (err: any) {
      setError(err?.message || "Failed to cancel job");
    } finally {
      setCancelling(false);
    }
  };

  const progressPct = job?.progress !== undefined ? Math.round(job.progress * 100) : 0;
  const stageText = job?.stage || "Initializing historical simulation...";

  return (
    <div
      className={`rounded-[var(--radius-md)] border border-purple-500/40 bg-[var(--bg-surface)] p-5 shadow-xl space-y-4 ${className}`}
    >
      <div className="flex items-center justify-between pb-3 border-b border-[var(--border-subtle)]">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-purple-400 animate-pulse" />
          <h3 className="text-sm font-bold text-white font-mono">
            Async Simulation Worker: #{jobId.slice(0, 8)}
          </h3>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono">
          <span
            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
              job?.status === "COMPLETED"
                ? "bg-emerald-500/20 text-emerald-300"
                : job?.status === "FAILED" || job?.status === "CANCELLED"
                ? "bg-rose-500/20 text-rose-300"
                : "bg-purple-500/20 text-purple-300 animate-pulse"
            }`}
          >
            {job?.status || "RUNNING"}
          </span>
        </div>
      </div>

      {error && (
        <div className="p-2.5 rounded bg-rose-500/20 border border-rose-500/30 text-rose-200 text-xs font-mono">
          {error}
        </div>
      )}

      {/* Stage Text & Percentage */}
      <div className="space-y-1.5 font-mono">
        <div className="flex justify-between text-xs">
          <span className="text-white font-medium">{stageText}</span>
          <span className="text-purple-300 font-bold">{progressPct}%</span>
        </div>

        <div className="w-full h-2 rounded-full overflow-hidden bg-[var(--bg-card)] border border-[var(--border-subtle)]">
          <div
            className="h-full bg-gradient-to-r from-purple-500 to-indigo-500 transition-all duration-300 rounded-full"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {/* Reproducibility Metadata Header (Section 7.5 requirement) */}
      <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-[var(--text-dim)] pt-2 border-t border-[var(--border-subtle)]">
        <div className="flex items-center gap-1.5 truncate">
          <GitBranch className="w-3 h-3 text-sky-400" />
          <span>Code: {job?.code_version || "v3.0.0"}</span>
        </div>
        <div className="flex items-center gap-1.5 truncate">
          <Hash className="w-3 h-3 text-purple-400" />
          <span>Config Hash: {job?.config_hash?.slice(0, 10) || "—"}</span>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between pt-2 border-t border-[var(--border-subtle)]">
        {job?.status === "COMPLETED" ? (
          <Link
            href={`/backtests/${jobId}`}
            className="flex items-center gap-1.5 text-xs font-mono font-bold text-emerald-400 hover:text-emerald-300 transition ml-auto"
          >
            <span>View Full Run Analysis</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        ) : job?.status === "FAILED" || job?.status === "CANCELLED" ? (
          <span className="text-xs font-mono text-rose-400">
            Simulation ended with status {job?.status}
          </span>
        ) : (
          <button
            type="button"
            onClick={handleCancel}
            disabled={cancelling}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] border border-rose-500/30 text-rose-300 hover:bg-rose-500/20 text-xs font-mono transition disabled:opacity-50"
          >
            <StopCircle className="w-3.5 h-3.5" />
            <span>Cancel Job</span>
          </button>
        )}
      </div>
    </div>
  );
}
