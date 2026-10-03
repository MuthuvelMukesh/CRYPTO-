import { Coins } from "lucide-react";

export default async function AssetDetailPage({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  const { symbol } = await params;
  const uppercaseSymbol = symbol.toUpperCase();

  return (
    <div className="space-y-4">
      <div className="pb-3 border-b border-[var(--border-subtle)] flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <span>{uppercaseSymbol}</span>
            <span className="text-xs px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 font-mono">
              Deep-Dive
            </span>
          </h1>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Candlestick chart, factor radar, technical breakdown, and explainability waterfall.
          </p>
        </div>
      </div>

      <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center">
        <Coins className="w-8 h-8 text-[var(--text-dim)] mx-auto mb-2" />
        <h3 className="text-sm font-semibold text-white">Asset Station: {uppercaseSymbol}</h3>
        <p className="text-xs text-[var(--text-muted)] mt-1 max-w-md mx-auto">
          Lightweight charts, order ticket preview, and factor telemetry configured for this pair.
        </p>
      </div>
    </div>
  );
}
