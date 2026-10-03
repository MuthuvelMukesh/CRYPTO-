"use client";

import React, { useEffect, useState, useCallback, use } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Bookmark,
  BookmarkCheck,
  TrendingUp,
  TrendingDown,
  Layers,
  Activity,
  AlertTriangle,
  RefreshCw,
  ShoppingCart,
  ExternalLink,
  ShieldCheck,
} from "lucide-react";

import { apiClient } from "@/lib/api/client";
import { formatPrice, formatPercent, formatScore, EMPTY_FALLBACK } from "@/lib/format";
import { ScoreBadge, FreshnessDot, DeltaCell, EmptyState, ErrorState, CardSkeleton } from "@/components/data";
import { RiskChip } from "@/components/data/RiskChip";
import { CandleChart, type CandleDataPoint } from "@/components/charts/CandleChart";
import { FactorRadarChart } from "@/components/charts/FactorRadarChart";
import { FeatureGlossaryTable, type FeatureRecord } from "@/components/domain/FeatureGlossaryTable";
import { ExplainPanel, type ExplainRankingItem } from "@/components/domain/ExplainPanel";
import { OrderTicketModal } from "@/components/domain/OrderTicketModal";

export default function AssetDetailPage() {
  const params = useParams();
  const router = useRouter();
  const rawSymbol = params?.symbol ? String(params.symbol) : "BTC";
  const symbol = rawSymbol.toUpperCase();

  const [timeframe, setTimeframe] = useState<string>("1h");
  const [assetInfo, setAssetInfo] = useState<any>(null);
  const [candles, setCandles] = useState<CandleDataPoint[]>([]);
  const [scoreData, setScoreData] = useState<any>(null);
  const [features, setFeatures] = useState<FeatureRecord | null>(null);
  const [scannerItem, setScannerItem] = useState<any>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isWatchlisted, setIsWatchlisted] = useState(false);
  const [orderModalOpen, setOrderModalOpen] = useState(false);

  // Check Watchlist in localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem("crypto_v3_watchlist");
      if (saved) {
        const list = JSON.parse(saved);
        if (Array.isArray(list) && list.includes(symbol)) {
          setIsWatchlisted(true);
        }
      }
    } catch {
      // Ignore localStorage errors
    }
  }, [symbol]);

  const toggleWatchlist = () => {
    try {
      const saved = localStorage.getItem("crypto_v3_watchlist");
      let list: string[] = saved ? JSON.parse(saved) : [];
      if (list.includes(symbol)) {
        list = list.filter((s) => s !== symbol);
        setIsWatchlisted(false);
      } else {
        list.push(symbol);
        setIsWatchlisted(true);
      }
      localStorage.setItem("crypto_v3_watchlist", JSON.stringify(list));
    } catch {
      // Ignore
    }
  };

  const fetchAssetData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // 1. Fetch Asset Detail
      const assetRes = await apiClient.GET("/api/v1/assets/{symbol}", {
        params: { path: { symbol } },
      });
      if (assetRes.data) {
        setAssetInfo(assetRes.data);
      }

      // 2. Fetch Historical OHLCV Candlesticks
      const ohlcvRes = await apiClient.GET("/api/v1/ohlcv/{symbol}", {
        params: {
          path: { symbol },
          query: {
            timeframe: timeframe as any,
            limit: 200,
          },
        },
      });
      if (ohlcvRes.data && Array.isArray(ohlcvRes.data)) {
        setCandles(ohlcvRes.data as CandleDataPoint[]);
      }

      // 3. Fetch Score Detail & Explainability
      try {
        const scoreRes = await apiClient.GET("/api/v1/scores/{symbol}", {
          params: { path: { symbol } },
        });
        if (scoreRes.data) {
          setScoreData(scoreRes.data);
        }
      } catch {
        // Score may not exist for newly registered pair
      }

      // 4. Fetch Calculated Quantitative Features
      try {
        const featRes = await apiClient.GET("/api/v1/assets/{symbol}/features", {
          params: {
            path: { symbol },
            query: {
              timeframe: timeframe as any,
            },
          },
        });
        if (featRes.data) {
          setFeatures(featRes.data as FeatureRecord);
        }
      } catch {
        // Features may still be generating
      }

      // 5. Fetch Scanner snapshot for current price & 24h delta
      try {
        const scanRes = await apiClient.GET("/api/v1/scanner/rankings", {
          params: {
            query: {
              search: symbol,
              limit: 1,
            },
          },
        });
        const items = (scanRes.data as any)?.items;
        if (Array.isArray(items) && items[0]) {
          setScannerItem(items[0]);
        }
      } catch {
        // Scanner item optional
      }
    } catch (err: any) {
      setError(err?.message || `Failed to retrieve intelligence for ${symbol}`);
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe]);

  useEffect(() => {
    fetchAssetData();
  }, [fetchAssetData]);

  // Derived price from candles or scanner snapshot
  const latestPrice =
    candles.length > 0 ? candles[candles.length - 1]?.close : scannerItem?.price ?? null;

  const return1dPct =
    scannerItem?.return_1d_pct !== undefined
      ? scannerItem.return_1d_pct
      : features?.return_1d !== undefined && features?.return_1d !== null
      ? features.return_1d * 100
      : null;

  return (
    <div className="space-y-6">
      {/* Top Navigation & Asset Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-[var(--border-subtle)] gap-4">
        <div className="flex items-center gap-3">
          <Link
            href="/scanner"
            className="p-2 rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-card)] text-[var(--text-muted)] hover:text-white hover:border-[var(--border-strong)] transition"
            title="Back to Scanner Rankings"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>

          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-extrabold tracking-tight text-white flex items-center gap-2">
                <span>{symbol}</span>
                <span className="text-xs px-2 py-0.5 rounded font-mono font-bold bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-secondary)]">
                  {assetInfo?.asset_class || "ALTCOIN"}
                </span>
                <span className="text-xs px-2 py-0.5 rounded font-mono text-sky-300 bg-sky-500/20 border border-sky-500/30">
                  {assetInfo?.primary_sector || "L1"}
                </span>
              </h1>
              <span className="text-xs text-[var(--text-muted)] hidden sm:inline">
                {assetInfo?.name || symbol}
              </span>
            </div>

            <div className="flex items-center gap-3 mt-1 text-xs font-mono">
              <div className="text-xl font-bold text-white">
                {formatPrice(latestPrice)}
              </div>
              <DeltaCell value={return1dPct} className="text-xs font-bold" />
              {scannerItem?.price_age_seconds !== undefined && (
                <div className="flex items-center gap-1 text-[var(--text-dim)] border-l border-[var(--border-subtle)] pl-2">
                  <FreshnessDot
                    timestamp={new Date(Date.now() - (scannerItem.price_age_seconds ?? 0) * 1000).toISOString()}
                    showLabel={true}
                  />
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Header Action Buttons */}
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={toggleWatchlist}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] border text-xs font-mono font-medium transition ${
              isWatchlisted
                ? "bg-amber-500/15 border-amber-500/40 text-amber-300"
                : "bg-[var(--bg-card)] border-[var(--border-subtle)] text-[var(--text-muted)] hover:text-white"
            }`}
          >
            {isWatchlisted ? (
              <BookmarkCheck className="w-3.5 h-3.5" />
            ) : (
              <Bookmark className="w-3.5 h-3.5" />
            )}
            <span>{isWatchlisted ? "Watchlisted" : "Add Watchlist"}</span>
          </button>

          <button
            type="button"
            onClick={() => setOrderModalOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-[var(--radius-sm)] bg-emerald-500 hover:bg-emerald-400 text-white text-xs font-mono font-bold transition shadow-lg shadow-emerald-500/20"
          >
            <ShoppingCart className="w-3.5 h-3.5" />
            <span>Paper Order Ticket</span>
          </button>
        </div>
      </div>

      {/* Risk Flags Bar if applicable */}
      {scoreData?.risk_flags && scoreData.risk_flags.length > 0 && (
        <div className="flex items-center gap-2 p-2.5 rounded-[var(--radius-sm)] bg-rose-500/10 border border-rose-500/25 text-xs text-rose-300">
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
          <span className="font-mono font-semibold uppercase text-[10px]">
            Risk Engine Penalties Applied:
          </span>
          <div className="flex flex-wrap gap-1.5">
            {scoreData.risk_flags.map((flag: string) => (
              <RiskChip key={flag} flag={flag} />
            ))}
          </div>
        </div>
      )}

      {error && (
        <ErrorState
          title={`Intelligence Unavailable for ${symbol}`}
          message={error}
          onRetry={fetchAssetData}
        />
      )}

      {loading && !error ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          <div className="lg:col-span-8">
            <CardSkeleton />
          </div>
          <div className="lg:col-span-4">
            <CardSkeleton />
          </div>
        </div>
      ) : (
        <>
          {/* Main Visuals Row: Candlestick Chart & Factor Radar */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            <div className="lg:col-span-8">
              <CandleChart
                candles={candles}
                symbol={symbol}
                timeframe={timeframe}
                onTimeframeChange={setTimeframe}
              />
            </div>

            <div className="lg:col-span-4">
              <FactorRadarChart
                trendScore={scoreData?.trend_score ?? scannerItem?.trend_score}
                momentumScore={scoreData?.momentum_score ?? scannerItem?.momentum_score}
                qualityScore={scoreData?.quality_score ?? scannerItem?.quality_score}
                liquidityScore={scoreData?.liquidity_score ?? scannerItem?.liquidity_score}
                relativeStrengthScore={
                  scoreData?.relative_strength_score ?? scannerItem?.relative_strength_score
                }
                opportunityScore={
                  scoreData?.opportunity_score ?? scannerItem?.opportunity_score
                }
              />
            </div>
          </div>

          {/* Secondary Intelligence Row: Quantitative Features & Explainability Breakdown */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            <div className="lg:col-span-7">
              <FeatureGlossaryTable features={features} />
            </div>

            <div className="lg:col-span-5">
              <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 flex flex-col h-full justify-between">
                <div>
                  <div className="flex items-center justify-between pb-2 mb-3 border-b border-[var(--border-subtle)]">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
                      Opportunity Score Explainability
                    </h3>
                    <ScoreBadge
                      score={scoreData?.opportunity_score ?? scannerItem?.opportunity_score}
                      partialData={scoreData?.partial_data ?? scannerItem?.partial_data}
                      size="sm"
                    />
                  </div>

                  {scoreData ? (
                    <div className="space-y-3">
                      {/* Factor Contributions */}
                      <div>
                        <span className="text-[10px] uppercase font-mono text-[var(--text-dim)] block mb-1">
                          Pillar Contributions (Net Gross)
                        </span>
                        <div className="space-y-1.5">
                          {Object.entries(scoreData.components || {}).map(
                            ([k, comp]: [string, any]) => (
                              <div
                                key={k}
                                className="flex items-center justify-between text-xs font-mono p-1.5 rounded bg-[var(--bg-card)]"
                              >
                                <span className="text-[var(--text-secondary)]">
                                  {comp.name || k}
                                </span>
                                <div className="flex items-center gap-2">
                                  <span className="text-[var(--text-dim)] text-[10px]">
                                    (wt: {(comp.weight * 100).toFixed(0)}%)
                                  </span>
                                  <span className="font-bold text-white">
                                    +{comp.contribution?.toFixed(1)}
                                  </span>
                                </div>
                              </div>
                            )
                          )}
                        </div>
                      </div>

                      {/* Penalties */}
                      {scoreData.penalties && scoreData.penalties.length > 0 && (
                        <div className="pt-2 border-t border-[var(--border-subtle)]">
                          <span className="text-[10px] uppercase font-mono text-rose-400 block mb-1">
                            Applied Deductions
                          </span>
                          <div className="space-y-1">
                            {scoreData.penalties.map((p: any, idx: number) => (
                              <div
                                key={idx}
                                className="flex items-center justify-between text-xs font-mono p-1.5 rounded bg-rose-500/10 text-rose-300"
                              >
                                <span>{p.flag}</span>
                                <span className="font-bold">
                                  -{p.deduction?.toFixed(1)}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {scoreData.explainability_summary && (
                        <div className="pt-2 border-t border-[var(--border-subtle)] text-[11px] text-[var(--text-muted)] italic">
                          "{scoreData.explainability_summary}"
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="py-8 text-center text-xs font-mono text-[var(--text-dim)]">
                      Detailed scoring breakdown pending pipeline batch run.
                    </div>
                  )}
                </div>

                <div className="pt-3 mt-3 border-t border-[var(--border-subtle)] flex items-center justify-between text-[10px] font-mono text-[var(--text-dim)]">
                  <span>Model: v3.0.0</span>
                  <span>Invariant 2 Guarded</span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Paper Order Ticket Modal */}
      <OrderTicketModal
        symbol={symbol}
        currentPrice={latestPrice}
        isStale={scannerItem ? !scannerItem.data_fresh : false}
        isOpen={orderModalOpen}
        onClose={() => setOrderModalOpen(false)}
        onSuccess={() => {
          // Trigger optional refresh or toast
        }}
      />
    </div>
  );
}
