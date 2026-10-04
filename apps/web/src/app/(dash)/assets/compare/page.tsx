"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  GitCompare,
  TrendingUp,
  Activity,
  Plus,
  X,
  RefreshCw,
  Layers,
  ArrowRight,
  ShieldAlert,
} from "lucide-react";

import { formatPrice, formatPercent, EMPTY_FALLBACK } from "@/lib/format";
import { FreshnessDot, CardSkeleton, ErrorState } from "@/components/data";

interface CorrelationRow {
  symbol: string;
  correlations: Record<string, number | null>;
}

interface AssetStat {
  symbol: string;
  current_price: number | null;
  volatility_annualized: number | null;
  sample_count: number;
}

interface CorrelationData {
  symbols: string[];
  timeframe: string;
  lookback_samples: number;
  matrix: CorrelationRow[];
  stats: AssetStat[];
  data_mode: string;
}

const AVAILABLE_SYMBOLS = [
  "BTC",
  "ETH",
  "SOL",
  "BNB",
  "AVAX",
  "LINK",
  "DOGE",
  "NEAR",
  "SUI",
  "APT",
];

export default function AssetComparePage() {
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>([
    "BTC",
    "ETH",
    "SOL",
    "BNB",
  ]);
  const [timeframe, setTimeframe] = useState<string>("1h");
  const [data, setData] = useState<CorrelationData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCorrelation = async () => {
    if (selectedSymbols.length < 2) return;
    setLoading(true);
    setError(null);
    try {
      const symParam = selectedSymbols.join(",");
      const res = await fetch(
        `/api/proxy/api/v1/analytics/correlation?symbols=${encodeURIComponent(
          symParam
        )}&timeframe=${timeframe}&limit=100`
      );
      if (!res.ok) {
        throw new Error(`Failed to calculate correlations (${res.status})`);
      }
      const json = await res.json();
      setData(json);
    } catch (err: any) {
      setError(err?.message || "Failed to load correlation data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCorrelation();
  }, [selectedSymbols, timeframe]);

  const handleAddSymbol = (sym: string) => {
    if (!selectedSymbols.includes(sym)) {
      setSelectedSymbols([...selectedSymbols, sym]);
    }
  };

  const handleRemoveSymbol = (sym: string) => {
    if (selectedSymbols.length <= 2) return; // Keep at least 2
    setSelectedSymbols(selectedSymbols.filter((s) => s !== sym));
  };

  const getHeatmapColor = (val: number | null | undefined) => {
    if (val === null || val === undefined) return "bg-slate-800/40 text-slate-500";
    if (val === 1.0) return "bg-cyan-500/30 text-cyan-300 font-bold border border-cyan-500/40";
    if (val >= 0.75) return "bg-emerald-500/25 text-emerald-300 font-semibold";
    if (val >= 0.5) return "bg-teal-500/20 text-teal-300";
    if (val >= 0.25) return "bg-sky-500/15 text-sky-300";
    if (val >= 0.0) return "bg-slate-800/60 text-slate-300";
    if (val >= -0.3) return "bg-amber-500/15 text-amber-300";
    return "bg-rose-500/25 text-rose-300 font-semibold";
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/40 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <GitCompare className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-3">
                Asset Compare & Correlation
                <span className="text-xs px-2.5 py-0.5 rounded-full font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                  {data?.data_mode || "HISTORICAL"}
                </span>
              </h1>
              <p className="text-xs text-muted-foreground mt-0.5">
                Multi-asset return correlation matrix, statistical dispersion, and cross-asset diversification analysis.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Timeframe selector */}
          <div className="flex items-center bg-card border border-border/60 rounded-lg p-1 text-xs">
            <button
              onClick={() => setTimeframe("1h")}
              className={`px-3 py-1 rounded font-medium transition-colors ${
                timeframe === "1h"
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              1H Returns
            </button>
            <button
              onClick={() => setTimeframe("1d")}
              className={`px-3 py-1 rounded font-medium transition-colors ${
                timeframe === "1d"
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              1D Returns
            </button>
          </div>

          <button
            onClick={fetchCorrelation}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-card hover:bg-accent text-xs text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Asset Selection Bar */}
      <div className="p-4 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-cyan-400" />
            Selected Portfolio Assets ({selectedSymbols.length})
          </span>
          <span className="text-xs text-muted-foreground">Select at least 2 assets for pairwise cross-correlation</span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {selectedSymbols.map((sym) => (
            <div
              key={sym}
              className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-semibold bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 shadow-sm"
            >
              <span>{sym}</span>
              {selectedSymbols.length > 2 && (
                <button
                  onClick={() => handleRemoveSymbol(sym)}
                  className="hover:text-rose-400 transition-colors ml-0.5"
                  title="Remove from comparison"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
          ))}

          {/* Add quick chip */}
          <div className="flex items-center gap-1 pl-2 border-l border-border/60">
            <span className="text-xs text-muted-foreground mr-1">Add:</span>
            {AVAILABLE_SYMBOLS.filter((s) => !selectedSymbols.includes(s)).slice(0, 5).map((s) => (
              <button
                key={s}
                onClick={() => handleAddSymbol(s)}
                className="px-2 py-0.5 rounded text-xs font-mono bg-muted/30 hover:bg-muted text-muted-foreground hover:text-foreground border border-border/40 transition-colors"
              >
                +{s}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <ErrorState
          title="Correlation Analysis Unavailable"
          message={error}
          onRetry={fetchCorrelation}
        />
      )}

      {loading && !data && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <CardSkeleton className="h-80" />
          <CardSkeleton className="h-80" />
        </div>
      )}

      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Heatmap Matrix (Spans 2 columns) */}
          <div className="lg:col-span-2 p-5 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold text-foreground">
                  Pearson Correlation Heatmap
                </h2>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Values close to +1.0 indicate locked co-movement; values near 0.0 or negative provide diversification benefit.
                </p>
              </div>
            </div>

            {/* Matrix Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-center border-collapse">
                <thead>
                  <tr>
                    <th className="p-2 text-left text-xs font-semibold text-muted-foreground uppercase">
                      Asset
                    </th>
                    {data.symbols.map((s) => (
                      <th
                        key={s}
                        className="p-2 text-xs font-mono font-semibold text-foreground uppercase border-b border-border/40"
                      >
                        {s}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.matrix.map((row) => (
                    <tr key={row.symbol} className="border-b border-border/20 hover:bg-accent/20 transition-colors">
                      <td className="p-2.5 text-left font-mono font-bold text-xs text-foreground">
                        {row.symbol}
                      </td>
                      {data.symbols.map((colSym) => {
                        const val = row.correlations[colSym];
                        return (
                          <td key={colSym} className="p-1.5">
                            <div
                              className={`py-2 px-1 rounded-md text-xs font-mono transition-transform hover:scale-105 cursor-default ${getHeatmapColor(
                                val
                              )}`}
                              title={`${row.symbol} vs ${colSym}: ${
                                val !== null && val !== undefined ? val.toFixed(4) : "Insufficient data"
                              }`}
                            >
                              {val !== null && val !== undefined ? val.toFixed(2) : EMPTY_FALLBACK}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Heatmap Legend */}
            <div className="flex flex-wrap items-center justify-between pt-2 border-t border-border/40 text-xs text-muted-foreground">
              <div className="flex items-center gap-2">
                <span>Legend:</span>
                <span className="px-2 py-0.5 rounded bg-emerald-500/25 text-emerald-300 font-mono text-xs">
                  &gt; +0.75 Co-moving
                </span>
                <span className="px-2 py-0.5 rounded bg-slate-800/80 text-slate-300 font-mono text-xs">
                  0.0 to 0.3 Decorrelated
                </span>
                <span className="px-2 py-0.5 rounded bg-rose-500/25 text-rose-300 font-mono text-xs">
                  &lt; 0.0 Inverse
                </span>
              </div>
              <span className="font-mono text-xs">Sample size: {data.lookback_samples} intervals</span>
            </div>
          </div>

          {/* Statistical Breakdown & Volatility */}
          <div className="p-5 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm space-y-4">
            <div>
              <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
                <Activity className="w-4 h-4 text-cyan-400" />
                Asset Volatility & Dispersion
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Annualized return volatility based on historical sample window.
              </p>
            </div>

            <div className="space-y-3">
              {data.stats.map((st) => (
                <div
                  key={st.symbol}
                  className="p-3 rounded-lg border border-border/40 bg-accent/10 hover:bg-accent/20 transition-colors flex items-center justify-between"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono font-bold text-sm text-foreground">
                      {st.symbol}
                    </span>
                    <span className="text-xs text-muted-foreground font-mono">
                      ${formatPrice(st.current_price)}
                    </span>
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <div className="text-xs font-mono font-semibold text-cyan-300">
                        {st.volatility_annualized !== null
                          ? `${(st.volatility_annualized * 100).toFixed(1)}% Vol`
                          : EMPTY_FALLBACK}
                      </div>
                      <div className="text-[10px] text-muted-foreground">
                        {st.sample_count} points
                      </div>
                    </div>

                    <Link
                      href={`/assets/${st.symbol.toLowerCase()}`}
                      className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                      title={`Open ${st.symbol} Deep-Dive`}
                    >
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                </div>
              ))}
            </div>

            {/* Diversification Insight */}
            <div className="p-3.5 rounded-lg border border-cyan-500/20 bg-cyan-500/5 text-xs text-cyan-200/90 leading-relaxed">
              <strong>Quant Insight:</strong> Combining pairs with correlation &lt; 0.6 significantly dampens portfolio variance without proportional sacrifice of return expectations under mean-variance optimization.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
