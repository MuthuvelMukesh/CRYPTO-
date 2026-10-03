"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Activity,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  ArrowRight,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  Info,
  Layers,
  Flame,
  CheckCircle2,
  XCircle,
  Clock,
  ExternalLink,
} from "lucide-react";

import { apiClient } from "@/lib/api/client";
import { formatPrice, formatPercent, formatRelativeTime, formatUTC, EMPTY_FALLBACK } from "@/lib/format";
import { ScoreBadge, FreshnessDot, DeltaCell, EmptyState, ErrorState, CardSkeleton } from "@/components/data";
import { RegimeBadge } from "@/components/domain/RegimeBadge";

interface RegimeData {
  data_mode: string;
  regime: string;
  confidence: number;
  btc_above_ema50: boolean;
  btc_above_ema200: boolean;
  btc_trend_slope: number;
  market_breadth_pct: number;
  eth_btc_ratio_trend: number;
  funding_sentiment: string;
  rationale: string[];
  btc_price?: number | null;
  eth_price?: number | null;
  btc_return_1d_pct?: number | null;
  eth_return_1d_pct?: number | null;
  checked_at: string;
}

interface TopAssetItem {
  asset_id: string;
  symbol: string;
  name: string;
  primary_sector: string;
  price: number | null;
  return_1d_pct: number | null;
  opportunity_score: number | null;
  partial_data: boolean;
  trend_score: number | null;
  momentum_score: number | null;
  quality_score: number | null;
  liquidity_score: number | null;
}

interface SectorItem {
  sector_name: string;
  asset_count: number;
  return_1d: number;
  return_7d: number;
  return_30d: number;
  breadth_pct: number;
  volume_change_7d_pct: number;
  rotation_status: string;
}

interface AlertItem {
  id?: string;
  alert_type: string;
  severity: string;
  asset_id?: string | null;
  message: string;
  time?: string;
}

export default function OverviewPage() {
  const [regime, setRegime] = useState<RegimeData | null>(null);
  const [topAssets, setTopAssets] = useState<TopAssetItem[]>([]);
  const [sectors, setSectors] = useState<SectorItem[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchOverviewData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      // 1. Fetch market regime
      const regimeRes = await apiClient.GET("/api/v1/scanner/regime");
      if (regimeRes.data) {
        setRegime(regimeRes.data as RegimeData);
      }

      // 2. Fetch top opportunities (ranked by opportunity score)
      const topRes = await apiClient.GET("/api/v1/scanner/rankings", {
        params: {
          query: {
            limit: 5,
            sort_by: "opportunity_score",
            sort_order: "desc",
          },
        },
      });
      if (topRes.data && "items" in topRes.data) {
        setTopAssets(topRes.data.items as unknown as TopAssetItem[]);
      }

      // 3. Fetch crypto sector rotation matrix
      const sectorsRes = await apiClient.GET("/api/v1/sectors");
      if (sectorsRes.data && Array.isArray(sectorsRes.data)) {
        setSectors(sectorsRes.data as SectorItem[]);
      }

      // 4. Fetch latest system alerts
      const alertsRes = await apiClient.GET("/api/v1/alerts", {
        params: {
          query: {
            limit: 5,
          },
        },
      });
      if (alertsRes.data && Array.isArray(alertsRes.data)) {
        setAlerts(alertsRes.data as unknown as AlertItem[]);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load market overview telemetry");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchOverviewData();
  }, [fetchOverviewData]);

  const getBreadthColor = (breadth: number) => {
    if (breadth >= 60) return "text-[var(--color-positive)]";
    if (breadth <= 40) return "text-[var(--color-negative)]";
    return "text-[var(--color-info)]";
  };

  const getBreadthLabel = (breadth: number) => {
    if (breadth >= 60) return "BULLISH EXPANSION";
    if (breadth <= 40) return "DEFENSIVE CONTRACTION";
    return "NEUTRAL CONSOLIDATION";
  };

  const getRotationColor = (status: string) => {
    switch (status.toUpperCase()) {
      case "LEADING":
        return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
      case "ACCELERATING":
        return "bg-sky-500/15 text-sky-400 border-sky-500/30";
      case "WEAKENING":
        return "bg-amber-500/15 text-amber-300 border-amber-500/30";
      case "DECLINING":
        return "bg-rose-500/15 text-rose-400 border-rose-500/30";
      default:
        return "bg-slate-700/30 text-slate-300 border-slate-600";
    }
  };

  const getAlertSeverityBadge = (severity: string) => {
    switch (severity.toUpperCase()) {
      case "CRITICAL":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40">
            <ShieldAlert className="w-3 h-3" />
            CRITICAL
          </span>
        );
      case "WARNING":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
            <AlertTriangle className="w-3 h-3" />
            WARNING
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-sky-500/20 text-sky-300 border border-sky-500/40">
            <Info className="w-3 h-3" />
            INFO
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[var(--border-subtle)] gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              Market Overview
            </h1>
            {regime?.data_mode && (
              <span className="text-[11px] font-mono font-semibold px-2 py-0.5 rounded bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-secondary)]">
                {regime.data_mode}
              </span>
            )}
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Macro state, universe breadth, benchmark tickers, and sector rotation matrix.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {regime?.checked_at && (
            <span
              className="text-[11px] font-mono text-[var(--text-dim)] flex items-center gap-1 mr-2"
              title={`Checked at UTC: ${formatUTC(regime.checked_at)}`}
            >
              <Clock className="w-3 h-3" />
              Updated {formatRelativeTime(regime.checked_at)}
            </span>
          )}
          <button
            type="button"
            onClick={() => fetchOverviewData(true)}
            disabled={refreshing || loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-card)] text-xs font-medium text-[var(--text-secondary)] hover:text-white hover:border-[var(--border-strong)] transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {error && (
        <ErrorState
          title="Market Overview Unavailable"
          message={error}
          onRetry={() => fetchOverviewData(false)}
        />
      )}

      {loading && !error ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : (
        <>
          {/* Top Row: Macro Regime & Universe Breadth */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {/* Macro Regime Card */}
            <div className="lg:col-span-8 rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-sky-400" />
                    <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
                      Macro Regime Telemetry
                    </h2>
                  </div>
                  <RegimeBadge
                    regime={regime?.regime}
                    confidence={regime?.confidence}
                    size="md"
                  />
                </div>

                {/* Confidence Bar */}
                <div className="mb-5">
                  <div className="flex justify-between items-center text-xs mb-1.5">
                    <span className="text-[var(--text-muted)]">Model Confidence</span>
                    <span className="font-mono text-white font-medium">
                      {regime?.confidence !== undefined
                        ? `${Math.round(regime.confidence <= 1 ? regime.confidence * 100 : regime.confidence)}%`
                        : EMPTY_FALLBACK}
                    </span>
                  </div>
                  <div className="w-full h-1.5 bg-[var(--bg-card)] rounded-full overflow-hidden border border-[var(--border-subtle)]">
                    <div
                      className="h-full bg-gradient-to-r from-sky-500 to-indigo-500 rounded-full transition-all duration-500"
                      style={{
                        width: `${
                          regime?.confidence
                            ? Math.min(
                                100,
                                Math.max(
                                  5,
                                  regime.confidence <= 1
                                    ? regime.confidence * 100
                                    : regime.confidence
                                )
                              )
                            : 0
                        }%`,
                      }}
                    />
                  </div>
                </div>

                {/* Macro Technical Signals Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-[var(--border-subtle)]">
                  <div className="rounded-[var(--radius-sm)] bg-[var(--bg-card)] p-2.5 border border-[var(--border-subtle)]">
                    <span className="text-[10px] text-[var(--text-dim)] uppercase block mb-1">
                      BTC 50 EMA
                    </span>
                    <div className="flex items-center gap-1.5 text-xs font-mono font-semibold">
                      {regime?.btc_above_ema50 ? (
                        <>
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                          <span className="text-emerald-300">ABOVE</span>
                        </>
                      ) : (
                        <>
                          <XCircle className="w-3.5 h-3.5 text-rose-400" />
                          <span className="text-rose-300">BELOW</span>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="rounded-[var(--radius-sm)] bg-[var(--bg-card)] p-2.5 border border-[var(--border-subtle)]">
                    <span className="text-[10px] text-[var(--text-dim)] uppercase block mb-1">
                      BTC 200 EMA
                    </span>
                    <div className="flex items-center gap-1.5 text-xs font-mono font-semibold">
                      {regime?.btc_above_ema200 ? (
                        <>
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                          <span className="text-emerald-300">ABOVE</span>
                        </>
                      ) : (
                        <>
                          <XCircle className="w-3.5 h-3.5 text-rose-400" />
                          <span className="text-rose-300">BELOW</span>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="rounded-[var(--radius-sm)] bg-[var(--bg-card)] p-2.5 border border-[var(--border-subtle)]">
                    <span className="text-[10px] text-[var(--text-dim)] uppercase block mb-1">
                      BTC Trend Slope
                    </span>
                    <span
                      className={`text-xs font-mono font-semibold ${
                        (regime?.btc_trend_slope ?? 0) >= 0
                          ? "text-emerald-400"
                          : "text-rose-400"
                      }`}
                    >
                      {regime?.btc_trend_slope !== undefined
                        ? (regime.btc_trend_slope > 0 ? "+" : "") +
                          regime.btc_trend_slope.toFixed(4)
                        : EMPTY_FALLBACK}
                    </span>
                  </div>

                  <div className="rounded-[var(--radius-sm)] bg-[var(--bg-card)] p-2.5 border border-[var(--border-subtle)]">
                    <span className="text-[10px] text-[var(--text-dim)] uppercase block mb-1">
                      Funding Bias
                    </span>
                    <span className="text-xs font-mono font-semibold text-white">
                      {regime?.funding_sentiment || "NEUTRAL"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Rationale Tag Chips */}
              <div className="mt-4 pt-3 border-t border-[var(--border-subtle)]">
                <span className="text-[10px] uppercase tracking-wider text-[var(--text-dim)] block mb-1.5">
                  Regime Classification Rationale
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {regime?.rationale && regime.rationale.length > 0 ? (
                    regime.rationale.map((tag) => (
                      <span
                        key={tag}
                        className="px-2 py-0.5 rounded text-[10px] font-mono bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-secondary)]"
                      >
                        {tag}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-[var(--text-dim)]">
                      Standard technical baseline
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Universe Breadth Gauge */}
            <div className="lg:col-span-4 rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Layers className="w-4 h-4 text-indigo-400" />
                    <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
                      Market Breadth
                    </h2>
                  </div>
                  <span className="text-[10px] font-mono text-[var(--text-muted)]">
                    7D Return &gt; 0
                  </span>
                </div>

                <div className="my-3 text-center">
                  <div
                    className={`text-4xl font-extrabold font-mono tracking-tight ${getBreadthColor(
                      regime?.market_breadth_pct ?? 50
                    )}`}
                  >
                    {regime?.market_breadth_pct !== undefined
                      ? `${regime.market_breadth_pct.toFixed(1)}%`
                      : EMPTY_FALLBACK}
                  </div>
                  <div className="mt-1 text-xs font-mono font-semibold tracking-wide text-white">
                    {getBreadthLabel(regime?.market_breadth_pct ?? 50)}
                  </div>
                </div>

                {/* Advancers vs Decliners Bar */}
                <div className="my-4">
                  <div className="flex justify-between text-[11px] font-mono mb-1 text-[var(--text-dim)]">
                    <span className="text-emerald-400">
                      Advancers: {regime?.market_breadth_pct?.toFixed(0) ?? 50}%
                    </span>
                    <span className="text-rose-400">
                      Decliners:{" "}
                      {regime?.market_breadth_pct !== undefined
                        ? (100 - regime.market_breadth_pct).toFixed(0)
                        : 50}
                      %
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full overflow-hidden bg-[var(--bg-card)] flex border border-[var(--border-subtle)]">
                    <div
                      className="bg-emerald-500 h-full transition-all duration-500"
                      style={{ width: `${regime?.market_breadth_pct ?? 50}%` }}
                    />
                    <div
                      className="bg-rose-500 h-full transition-all duration-500"
                      style={{
                        width: `${100 - (regime?.market_breadth_pct ?? 50)}%`,
                      }}
                    />
                  </div>
                </div>
              </div>

              <div className="rounded-[var(--radius-sm)] bg-[var(--bg-card)] p-3 border border-[var(--border-subtle)] text-[11px] text-[var(--text-muted)]">
                <span className="text-white font-medium block mb-0.5">
                  Universe Participation
                </span>
                Percentage of scanned universe assets sustaining positive momentum over
                the 7-day trailing cycle.
              </div>
            </div>
          </div>

          {/* Benchmark Ticker Cards: BTC & ETH (Strict Invariant 2: No Fabricated Deltas) */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* BTC Card */}
            <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 flex items-center justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-amber-500/20 border border-amber-500/40 text-amber-400 flex items-center justify-center font-bold text-xs">
                    ₿
                  </span>
                  <div>
                    <h3 className="text-sm font-bold text-white tracking-wide">
                      Bitcoin
                    </h3>
                    <span className="text-[10px] font-mono text-[var(--text-dim)]">
                      BTC/USDT Benchmark
                    </span>
                  </div>
                </div>
                <div className="text-2xl font-extrabold font-mono text-white mt-1">
                  {formatPrice(regime?.btc_price)}
                </div>
              </div>

              <div className="text-right space-y-1.5">
                <span className="text-[10px] uppercase font-mono text-[var(--text-dim)] block">
                  1D Delta
                </span>
                {regime?.btc_return_1d_pct !== null &&
                regime?.btc_return_1d_pct !== undefined ? (
                  <DeltaCell
                    value={regime.btc_return_1d_pct}
                    className="text-base font-bold font-mono"
                  />
                ) : (
                  <div className="text-xs font-mono text-[var(--text-dim)]" title="Comparison window has fewer than 24 hourly candles">
                    — <span className="text-[10px] opacity-75">(pending history)</span>
                  </div>
                )}
                <div className="text-[10px] font-mono text-[var(--text-secondary)]">
                  {regime?.btc_above_ema50 ? "Trend: Bullish" : "Trend: Defensive"}
                </div>
              </div>
            </div>

            {/* ETH Card */}
            <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 flex items-center justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-indigo-500/20 border border-indigo-500/40 text-indigo-400 flex items-center justify-center font-bold text-xs">
                    Ξ
                  </span>
                  <div>
                    <h3 className="text-sm font-bold text-white tracking-wide">
                      Ethereum
                    </h3>
                    <span className="text-[10px] font-mono text-[var(--text-dim)]">
                      ETH/USDT Benchmark
                    </span>
                  </div>
                </div>
                <div className="text-2xl font-extrabold font-mono text-white mt-1">
                  {formatPrice(regime?.eth_price)}
                </div>
              </div>

              <div className="text-right space-y-1.5">
                <span className="text-[10px] uppercase font-mono text-[var(--text-dim)] block">
                  1D Delta
                </span>
                {regime?.eth_return_1d_pct !== null &&
                regime?.eth_return_1d_pct !== undefined ? (
                  <DeltaCell
                    value={regime.eth_return_1d_pct}
                    className="text-base font-bold font-mono"
                  />
                ) : (
                  <div className="text-xs font-mono text-[var(--text-dim)]" title="Comparison window has fewer than 24 hourly candles">
                    — <span className="text-[10px] opacity-75">(pending history)</span>
                  </div>
                )}
                <div className="text-[10px] font-mono text-[var(--text-secondary)]">
                  ETH/BTC: {regime?.eth_btc_ratio_trend !== undefined ? (regime.eth_btc_ratio_trend > 0 ? "+RS" : "-RS") : "—"}
                </div>
              </div>
            </div>
          </div>

          {/* Middle Grid: Top Opportunities & Mini Sector Heatmap */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {/* Top Opportunities Card */}
            <div className="lg:col-span-7 rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5">
              <div className="flex items-center justify-between mb-4 pb-2 border-b border-[var(--border-subtle)]">
                <div className="flex items-center gap-2">
                  <Flame className="w-4 h-4 text-amber-400" />
                  <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
                    Top Opportunities
                  </h2>
                </div>
                <Link
                  href="/scanner"
                  className="text-xs text-sky-400 hover:text-sky-300 font-medium flex items-center gap-1 transition"
                >
                  <span>Open Scanner</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>

              {topAssets.length === 0 ? (
                <EmptyState
                  title="No Opportunities Scored"
                  description="Run the scanner pipeline or wait for ingestion to populate rankings."
                />
              ) : (
                <div className="divide-y divide-[var(--border-subtle)]">
                  {topAssets.map((asset, idx) => (
                    <div
                      key={asset.asset_id || asset.symbol}
                      className="py-3 first:pt-0 last:pb-0 flex items-center justify-between gap-3 hover:bg-[var(--bg-card)]/40 px-2 rounded-[var(--radius-sm)] transition"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-xs font-mono text-[var(--text-dim)] w-4 text-right">
                          {idx + 1}
                        </span>
                        <div>
                          <div className="flex items-center gap-2">
                            <Link
                              href={`/assets/${asset.symbol}`}
                              className="font-bold text-sm text-white hover:text-sky-400 transition"
                            >
                              {asset.symbol}
                            </Link>
                            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-muted)]">
                              {asset.primary_sector || "L1"}
                            </span>
                          </div>
                          <span className="text-[11px] text-[var(--text-dim)] truncate block max-w-[120px] sm:max-w-[180px]">
                            {asset.name}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-4 text-right">
                        <div>
                          <div className="text-xs font-mono font-semibold text-white">
                            {formatPrice(asset.price)}
                          </div>
                          <DeltaCell value={asset.return_1d_pct} isFraction={false} />
                        </div>

                        <div className="w-20 flex justify-end">
                          <ScoreBadge
                            score={asset.opportunity_score}
                            partialData={asset.partial_data}
                            size="sm"
                          />
                        </div>

                        <Link
                          href={`/assets/${asset.symbol}`}
                          className="p-1 rounded text-[var(--text-muted)] hover:text-white hover:bg-[var(--bg-card)] transition"
                          title={`Deep dive ${asset.symbol}`}
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Mini Sector Heatmap Card */}
            <div className="lg:col-span-5 rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5">
              <div className="flex items-center justify-between mb-4 pb-2 border-b border-[var(--border-subtle)]">
                <div className="flex items-center gap-2">
                  <Layers className="w-4 h-4 text-emerald-400" />
                  <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
                    Sector Heatmap
                  </h2>
                </div>
                <Link
                  href="/sectors"
                  className="text-xs text-sky-400 hover:text-sky-300 font-medium flex items-center gap-1 transition"
                >
                  <span>Rotation Matrix</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>

              {sectors.length === 0 ? (
                <EmptyState
                  title="No Sector Data"
                  description="Sector metrics will compute once multi-asset feature sets are synchronized."
                />
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {sectors.slice(0, 6).map((sec) => (
                    <div
                      key={sec.sector_name}
                      className="rounded-[var(--radius-sm)] bg-[var(--bg-card)] p-3 border border-[var(--border-subtle)] flex flex-col justify-between hover:border-[var(--border-strong)] transition"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-bold text-white tracking-wide">
                          {sec.sector_name}
                        </span>
                        <span
                          className={`text-[9px] font-mono font-semibold px-1.5 py-0.5 rounded border ${getRotationColor(
                            sec.rotation_status
                          )}`}
                        >
                          {sec.rotation_status}
                        </span>
                      </div>

                      <div className="flex justify-between items-baseline text-xs font-mono">
                        <span className="text-[10px] text-[var(--text-dim)]">1D / 7D</span>
                        <div className="flex items-center gap-1.5">
                          <DeltaCell value={sec.return_1d} isFraction={true} decimals={1} />
                          <span className="text-[var(--text-dim)]">/</span>
                          <DeltaCell value={sec.return_7d} isFraction={true} decimals={1} />
                        </div>
                      </div>

                      <div className="mt-2 pt-2 border-t border-[var(--border-subtle)] flex justify-between items-center text-[10px] font-mono text-[var(--text-dim)]">
                        <span>Breadth: {sec.breadth_pct.toFixed(0)}%</span>
                        <span>{sec.asset_count} coins</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Bottom Row: Latest Alerts Feed */}
          <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5">
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-[var(--border-subtle)]">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-rose-400" />
                <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
                  Latest Alerts &amp; Signals
                </h2>
              </div>
              <Link
                href="/alerts"
                className="text-xs text-sky-400 hover:text-sky-300 font-medium flex items-center gap-1 transition"
              >
                <span>View All Alerts</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {alerts.length === 0 ? (
              <div className="py-6 text-center text-xs text-[var(--text-dim)] font-mono">
                No alerts triggered in current evaluation cycle.
              </div>
            ) : (
              <div className="divide-y divide-[var(--border-subtle)]">
                {alerts.map((alert, i) => (
                  <div
                    key={alert.id || `${alert.asset_id || "ALERT"}-${i}`}
                    className="py-2.5 first:pt-1 last:pb-1 flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                  >
                    <div className="flex items-center gap-2.5">
                      {getAlertSeverityBadge(alert.severity)}
                      <span className="font-bold text-xs font-mono text-white">
                        {alert.asset_id || "SYSTEM"}
                      </span>
                      <span className="text-xs text-[var(--text-secondary)]">
                        {alert.message}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 text-right shrink-0">
                      <span
                        className="text-[10px] font-mono text-[var(--text-dim)]"
                        title={formatUTC(alert.time)}
                      >
                        {formatRelativeTime(alert.time)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
