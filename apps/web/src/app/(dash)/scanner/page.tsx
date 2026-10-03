"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import {
  RefreshCw,
  Download,
  Filter,
  Radio,
  SlidersHorizontal,
  Flame,
  ShieldAlert,
  ArrowUpDown,
} from "lucide-react";

import { formatPrice, formatPercent, formatScore, EMPTY_FALLBACK } from "@/lib/format";
import {
  DataTable,
  ScoreBadge,
  FreshnessDot,
  DeltaCell,
  Sparkline,
  EmptyState,
  ErrorState,
} from "@/components/data";
import { RiskChip } from "@/components/data/RiskChip";
import { ExplainPanel, type ExplainRankingItem } from "@/components/domain/ExplainPanel";
import { useEventStream } from "@/hooks/useEventStream";

interface RankingItem extends ExplainRankingItem {
  asset_id: string;
  price_age_seconds?: number | null;
  data_fresh: boolean;
  return_1d_pct?: number | null;
  return_7d_pct?: number | null;
  return_30d_pct?: number | null;
  sparkline_7d?: number[];
  flash?: "up" | "down" | null;
}

export default function ScannerPage() {
  const [rankings, setRankings] = useState<RankingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<any>(null);
  const [selectedItem, setSelectedItem] = useState<RankingItem | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [rescanLoading, setRescanLoading] = useState(false);

  // Filters State
  const [sectorFilter, setSectorFilter] = useState<string>("ALL");
  const [assetClassFilter, setAssetClassFilter] = useState<string>("ALL");
  const [minScore, setMinScore] = useState<number>(0);
  const [excludeRiskFlags, setExcludeRiskFlags] = useState<boolean>(false);
  const [hideStale, setHideStale] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Fetch rankings from API proxy
  const fetchRankings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("limit", "100");
      params.set("sort_by", "opportunity_score");
      params.set("sort_order", "desc");
      if (sectorFilter !== "ALL") params.set("sector", sectorFilter);
      if (assetClassFilter !== "ALL") params.set("asset_class", assetClassFilter);
      if (minScore > 0) params.set("min_score", String(minScore));
      if (hideStale) params.set("data_fresh_only", "true");

      const res = await fetch(`/api/proxy/api/v1/scanner/rankings?${params.toString()}`);
      if (!res.ok) {
        const errorJson = await res.json().catch(() => null);
        throw errorJson || new Error(`Scanner error ${res.status}`);
      }

      const data = await res.json();
      const items: RankingItem[] = (data.rankings || []).map((r: any) => ({
        ...r,
        sparkline_7d: r.sparkline_7d || [
          r.price ? r.price * (1 - (r.return_7d_pct || 0) / 100) : 100,
          r.price ? r.price * (1 - (r.return_1d_pct || 0) / 100) : 102,
          r.price || 105,
        ],
      }));

      setRankings(items);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [sectorFilter, assetClassFilter, minScore, hideStale]);

  useEffect(() => {
    fetchRankings();
  }, [fetchRankings]);

  // Live SSE Stream handler
  const { status: sseStatus, isPaused, togglePause } = useEventStream<{
    symbol?: string;
    opportunity_score?: number;
    price?: number;
    rankings?: any[];
  }>({
    url: "/api/proxy/api/v1/stream/scanner",
    enabled: true,
    onMessage: (msg) => {
      if (msg.rankings && Array.isArray(msg.rankings)) {
        // Bulk snapshot update
        setRankings((prev) => {
          const map = new Map(prev.map((i) => [i.symbol, i]));
          msg.rankings?.forEach((newItem: any) => {
            const existing = map.get(newItem.symbol);
            const oldPrice = existing?.price || 0;
            const newPrice = newItem.price || 0;
            const flash = newPrice > oldPrice ? "up" : newPrice < oldPrice ? "down" : null;
            map.set(newItem.symbol, { ...existing, ...newItem, flash });
          });
          return Array.from(map.values());
        });
      } else if (msg.symbol) {
        // Single symbol tick update
        setRankings((prev) =>
          prev.map((item) => {
            if (item.symbol === msg.symbol) {
              const oldPrice = item.price || 0;
              const newPrice = msg.price ?? oldPrice;
              const flash = newPrice > oldPrice ? "up" : newPrice < oldPrice ? "down" : null;
              return {
                ...item,
                price: newPrice,
                opportunity_score: msg.opportunity_score ?? item.opportunity_score,
                flash,
              };
            }
            return item;
          })
        );
      }
    },
  });

  // Rescan on-demand action
  const handleRescan = async () => {
    setRescanLoading(true);
    try {
      await fetch("/api/proxy/api/v1/scanner/rescan", { method: "POST" });
      await fetchRankings();
    } catch (err) {
      console.error("Rescan failed", err);
    } finally {
      setRescanLoading(false);
    }
  };

  // CSV Export utility
  const handleExportCSV = () => {
    if (rankings.length === 0) return;
    const headers = [
      "Symbol",
      "Name",
      "Sector",
      "Asset Class",
      "Price",
      "1D %",
      "7D %",
      "30D %",
      "Score",
      "Partial Data",
      "Risk Flags",
    ];

    const rows = filteredRankings.map((r) => [
      r.symbol,
      `"${r.name}"`,
      r.primary_sector,
      r.asset_class,
      r.price !== null && r.price !== undefined ? r.price : "",
      r.return_1d_pct !== null && r.return_1d_pct !== undefined ? r.return_1d_pct : "",
      r.return_7d_pct !== null && r.return_7d_pct !== undefined ? r.return_7d_pct : "",
      r.return_30d_pct !== null && r.return_30d_pct !== undefined ? r.return_30d_pct : "",
      r.opportunity_score !== null && r.opportunity_score !== undefined ? r.opportunity_score : "",
      r.partial_data ? "TRUE" : "FALSE",
      `"${(r.risk_flags || []).join(", ")}"`,
    ]);

    const csvContent =
      "data:text/csv;charset=utf-8," +
      [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute(
      "download",
      `scanner_rankings_${new Date().toISOString().split("T")[0]}.csv`
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Client-side filtering
  const filteredRankings = useMemo(() => {
    return rankings.filter((item) => {
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const matchesSymbol = item.symbol.toLowerCase().includes(query);
        const matchesName = item.name.toLowerCase().includes(query);
        if (!matchesSymbol && !matchesName) return false;
      }
      if (excludeRiskFlags && item.risk_flags && item.risk_flags.length > 0) {
        return false;
      }
      return true;
    });
  }, [rankings, searchQuery, excludeRiskFlags]);

  // Table Columns Definition
  const columns: ColumnDef<RankingItem>[] = useMemo(
    () => [
      {
        accessorKey: "symbol",
        header: "Asset",
        size: 160,
        cell: ({ row }) => {
          const item = row.original;
          return (
            <div className="flex items-center gap-2">
              <FreshnessDot timestamp={item.candle_time} />
              <div className="flex flex-col min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="font-bold text-white font-mono text-xs">{item.symbol}</span>
                  <span className="text-[10px] font-mono px-1 py-0.2 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 uppercase">
                    {item.primary_sector}
                  </span>
                </div>
                <span className="text-[11px] text-[var(--text-muted)] truncate max-w-[130px]">
                  {item.name}
                </span>
              </div>
            </div>
          );
        },
      },
      {
        accessorKey: "price",
        header: () => <div className="text-right">Price</div>,
        size: 110,
        cell: ({ row }) => {
          const item = row.original;
          const flashClass =
            item.flash === "up" ? "flash-up text-emerald-400" : item.flash === "down" ? "flash-down text-rose-400" : "";
          return (
            <div className={`text-right font-mono tabular-nums text-xs font-semibold text-white ${flashClass}`}>
              {formatPrice(item.price)}
            </div>
          );
        },
      },
      {
        accessorKey: "return_1d_pct",
        header: () => <div className="text-right">1D %</div>,
        size: 85,
        cell: ({ getValue }) => <DeltaCell value={getValue() as number} className="justify-end w-full" />,
      },
      {
        accessorKey: "return_7d_pct",
        header: () => <div className="text-right">7D %</div>,
        size: 85,
        cell: ({ getValue }) => <DeltaCell value={getValue() as number} className="justify-end w-full" />,
      },
      {
        accessorKey: "return_30d_pct",
        header: () => <div className="text-right">30D %</div>,
        size: 85,
        cell: ({ getValue }) => <DeltaCell value={getValue() as number} className="justify-end w-full" />,
      },
      {
        accessorKey: "opportunity_score",
        header: () => <div className="text-center">Score</div>,
        size: 140,
        cell: ({ row }) => {
          const item = row.original;
          return (
            <div className="flex justify-center">
              <ScoreBadge
                score={item.opportunity_score}
                partialData={item.partial_data}
                showBar={true}
              />
            </div>
          );
        },
      },
      {
        id: "factors",
        header: "Factor Highlights",
        size: 150,
        cell: ({ row }) => {
          const components = row.original.score_breakdown?.components;
          if (!components) return <span className="font-mono text-[var(--text-dim)]">{EMPTY_FALLBACK}</span>;

          const mom = components.momentum?.score;
          const vol = components.volume_acceleration?.score;
          const liq = components.liquidity?.score;

          return (
            <div className="flex items-center gap-2 font-mono text-[11px] text-[var(--text-muted)]">
              <span title="Momentum Score">M:<strong className="text-white">{formatScore(mom)}</strong></span>
              <span>&bull;</span>
              <span title="Volume Acceleration">V:<strong className="text-white">{formatScore(vol)}</strong></span>
              <span>&bull;</span>
              <span title="Liquidity Score">L:<strong className="text-white">{formatScore(liq)}</strong></span>
            </div>
          );
        },
      },
      {
        accessorKey: "risk_flags",
        header: "Risk Flags",
        size: 140,
        cell: ({ getValue }) => {
          const flags = (getValue() as string[]) || [];
          if (flags.length === 0) {
            return (
              <span className="text-[10px] font-mono text-emerald-400/80 px-1 py-0.5 rounded bg-emerald-500/10">
                CLEAN
              </span>
            );
          }
          return (
            <div className="flex flex-wrap gap-1">
              {flags.slice(0, 2).map((f) => (
                <RiskChip key={f} flag={f} />
              ))}
              {flags.length > 2 && (
                <span className="text-[10px] font-mono text-[var(--text-dim)]">
                  +{flags.length - 2}
                </span>
              )}
            </div>
          );
        },
      },
      {
        id: "sparkline",
        header: () => <div className="text-center">7D Trend</div>,
        size: 90,
        cell: ({ row }) => (
          <div className="flex justify-center">
            <Sparkline data={row.original.sparkline_7d} width={76} height={20} />
          </div>
        ),
      },
    ],
    []
  );

  return (
    <div className="space-y-4">
      {/* Page Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 pb-3 border-b border-[var(--border-subtle)]">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            Market Scanner
            <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-mono font-medium">
              Live Workstation
            </span>
          </h1>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Cross-sectional momentum, volume acceleration, liquidity, and regime scoring. Click any row for factor attribution.
          </p>
        </div>

        {/* Global Toolbar */}
        <div className="flex flex-wrap items-center gap-2">
          {/* SSE Stream State & Toggle */}
          <button
            type="button"
            onClick={togglePause}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-[var(--radius-sm)] border text-xs font-mono font-semibold transition ${
              isPaused
                ? "bg-amber-500/10 border-amber-500/30 text-amber-300"
                : "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
            }`}
            title="Toggle live SSE updates"
          >
            <Radio className={`w-3.5 h-3.5 ${!isPaused ? "animate-pulse" : ""}`} />
            <span>{isPaused ? "Stream: Paused" : "Stream: Live"}</span>
          </button>

          {/* CSV Export */}
          <button
            type="button"
            onClick={handleExportCSV}
            disabled={rankings.length === 0}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs text-[var(--text-secondary)] hover:text-white transition disabled:opacity-50"
            title="Export rankings table as CSV"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>

          {/* Rescan Button */}
          <button
            type="button"
            onClick={handleRescan}
            disabled={rescanLoading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold transition shadow-md shadow-indigo-600/20"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${rescanLoading ? "animate-spin" : ""}`} />
            <span>{rescanLoading ? "Scanning..." : "Rescan Universe"}</span>
          </button>
        </div>
      </div>

      {/* Filter Control Bar */}
      <div className="p-3 rounded-[var(--radius-md)] bg-[var(--bg-surface)] border border-[var(--border-subtle)] flex flex-wrap items-center gap-3 text-xs">
        {/* Sector Filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-[var(--text-muted)] font-medium">Sector:</span>
          <select
            value={sectorFilter}
            onChange={(e) => setSectorFilter(e.target.value)}
            className="px-2.5 py-1 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-strong)] text-white text-xs focus:outline-none font-mono"
          >
            <option value="ALL">All Sectors</option>
            <option value="L1">Layer 1 (L1)</option>
            <option value="DeFi">DeFi</option>
            <option value="AI">AI & Compute</option>
            <option value="Meme">Meme</option>
            <option value="Infra">Infrastructure</option>
          </select>
        </div>

        {/* Asset Class Filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-[var(--text-muted)] font-medium">Class:</span>
          <select
            value={assetClassFilter}
            onChange={(e) => setAssetClassFilter(e.target.value)}
            className="px-2.5 py-1 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-strong)] text-white text-xs focus:outline-none font-mono"
          >
            <option value="ALL">All Classes</option>
            <option value="CORE">Core</option>
            <option value="ALTCOIN">Altcoin</option>
            <option value="MEME">Meme</option>
            <option value="SMALLCAP">Small Cap</option>
          </select>
        </div>

        {/* Min Score Filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-[var(--text-muted)] font-medium">Min Score:</span>
          <input
            type="number"
            min="0"
            max="100"
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="w-16 px-2 py-1 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-strong)] text-white text-xs font-mono focus:outline-none text-center"
          />
        </div>

        {/* Exclude Risk Flags */}
        <label className="flex items-center gap-1.5 cursor-pointer text-[var(--text-secondary)] select-none">
          <input
            type="checkbox"
            checked={excludeRiskFlags}
            onChange={(e) => setExcludeRiskFlags(e.target.checked)}
            className="rounded border-[var(--border-strong)] text-indigo-600 focus:ring-0"
          />
          <span>Exclude Risk Flags</span>
        </label>

        {/* Hide Stale */}
        <label className="flex items-center gap-1.5 cursor-pointer text-[var(--text-secondary)] select-none">
          <input
            type="checkbox"
            checked={hideStale}
            onChange={(e) => setHideStale(e.target.checked)}
            className="rounded border-[var(--border-strong)] text-indigo-600 focus:ring-0"
          />
          <span>Hide Stale Data</span>
        </label>
      </div>

      {/* Main Table or Error State */}
      {error ? (
        <ErrorState
          problem={error}
          title="Scanner API Unavailable"
          onRetry={fetchRankings}
        />
      ) : (
        <DataTable
          columns={columns}
          data={filteredRankings}
          loading={loading}
          searchPlaceholder="Search by symbol or name..."
          onRowClick={(item) => {
            setSelectedItem(item);
            setDrawerOpen(true);
          }}
          selectedRowId={selectedItem?.symbol}
          getRowId={(r) => r.symbol}
          emptyTitle="No Assets Match Criteria"
          emptyDescription="Try adjusting sector filters, minimum score, or click Rescan Universe to fetch market data."
        />
      )}

      {/* Right Slide-over Explainability Drawer */}
      <ExplainPanel
        item={selectedItem}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}
