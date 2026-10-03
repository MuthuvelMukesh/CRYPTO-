"use client";

interface TableSkeletonProps {
  rows?: number;
  columns?: number;
  className?: string;
}

export function TableSkeleton({
  rows = 10,
  columns = 8,
  className = "",
}: TableSkeletonProps) {
  return (
    <div
      className={`w-full rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] overflow-hidden animate-pulse ${className}`}
      aria-busy="true"
      aria-label="Loading table records"
    >
      {/* Table Header Placeholder */}
      <div className="h-10 bg-[var(--bg-card)] border-b border-[var(--border-subtle)] flex items-center px-4 gap-4">
        {Array.from({ length: columns }).map((_, i) => (
          <div
            key={`th-${i}`}
            className="h-3.5 bg-slate-700/50 rounded flex-1 max-w-[120px]"
          />
        ))}
      </div>

      {/* Table Rows Placeholder */}
      <div className="divide-y divide-[var(--border-subtle)]">
        {Array.from({ length: rows }).map((_, rowIdx) => (
          <div
            key={`tr-${rowIdx}`}
            className="h-11 flex items-center px-4 gap-4"
          >
            {Array.from({ length: columns }).map((_, colIdx) => (
              <div
                key={`td-${rowIdx}-${colIdx}`}
                className={`h-3 bg-slate-800/80 rounded flex-1 ${
                  colIdx === 0
                    ? "max-w-[80px]"
                    : colIdx === 1
                    ? "max-w-[140px]"
                    : "max-w-[100px]"
                }`}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

interface CardSkeletonProps {
  className?: string;
}

export function CardSkeleton({ className = "" }: CardSkeletonProps) {
  return (
    <div
      className={`rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 animate-pulse ${className}`}
      aria-busy="true"
    >
      <div className="h-3 bg-slate-800 rounded w-24 mb-3" />
      <div className="h-7 bg-slate-700/60 rounded w-36 mb-2" />
      <div className="h-2.5 bg-slate-800/80 rounded w-48" />
    </div>
  );
}

interface ChartSkeletonProps {
  height?: number;
  className?: string;
}

export function ChartSkeleton({ height = 320, className = "" }: ChartSkeletonProps) {
  return (
    <div
      className={`w-full rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 flex flex-col justify-between animate-pulse ${className}`}
      style={{ height }}
      aria-busy="true"
      aria-label="Loading chart visualisation"
    >
      <div className="flex items-center justify-between">
        <div className="h-4 bg-slate-800 rounded w-32" />
        <div className="flex gap-2">
          <div className="h-6 bg-slate-800 rounded w-12" />
          <div className="h-6 bg-slate-800 rounded w-12" />
        </div>
      </div>

      <div className="w-full flex items-end gap-2 h-44 px-4">
        {Array.from({ length: 24 }).map((_, i) => (
          <div
            key={`bar-${i}`}
            className="flex-1 bg-slate-800/50 rounded-t"
            style={{ height: `${20 + ((i * 17) % 70)}%` }}
          />
        ))}
      </div>

      <div className="h-3 bg-slate-800/60 rounded w-full" />
    </div>
  );
}
