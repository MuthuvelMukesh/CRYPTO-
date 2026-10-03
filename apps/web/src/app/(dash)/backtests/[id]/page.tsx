import { FlaskConical } from "lucide-react";

export default async function BacktestDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <div className="space-y-4">
      <div className="pb-3 border-b border-[var(--border-subtle)]">
        <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
          <span>Backtest #{id}</span>
          <span className="text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-mono">
            Run Analysis
          </span>
        </h1>
        <p className="text-xs text-[var(--text-muted)] mt-0.5">
          Detailed metrics, underwater drawdown, regime breakdown, and execution trade log.
        </p>
      </div>

      <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center">
        <FlaskConical className="w-8 h-8 text-[var(--text-dim)] mx-auto mb-2" />
        <h3 className="text-sm font-semibold text-white">Backtest Report: {id}</h3>
        <p className="text-xs text-[var(--text-muted)] mt-1 max-w-md mx-auto">
          Loading metrics grid, monthly return matrix, and Monte Carlo bootstrap intervals.
        </p>
      </div>
    </div>
  );
}
