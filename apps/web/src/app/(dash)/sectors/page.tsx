"use client";

import React, { useState, useEffect } from "react";
import {
  PieChart,
  TrendingUp,
  Layers,
  RefreshCw,
  ArrowRight,
  X,
  ExternalLink,
} from "lucide-react";
import Link from "next/link";
import { formatPercent, formatCompactUSD, EMPTY_FALLBACK } from "@/lib/format";
import { DeltaCell, ScoreBadge } from "@/components/data";
import { SectorRotationChart, SectorItem } from "@/components/charts/SectorRotationChart";

interface SectorConstituent {
  symbol: string;
  name: string;
  price_usd: number;
  return_24h: number;
  opportunity_score: number;
}

export default function SectorsPage() {
  const [loading, setLoading] = useState(true);
  const [sectors, setSectors] = useState<SectorItem[]>([]);
  const [selectedSector, setSelectedSector] = useState<SectorItem | null>(null);
  const [constituents, setConstituents] = useState<SectorConstituent[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const fetchSectors = async () => {
    setLoading(true);
    try {
      const url = statusFilter !== "ALL"
        ? `/api/proxy/api/v1/sectors?rotation_status=${statusFilter}`
        : "/api/proxy/api/v1/sectors";
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setSectors(data);
      }
    } catch {
      // Handled via state
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSectors();
  }, [statusFilter]);

  // When a sector is selected, mock/fetch constituents from scanner API
  useEffect(() => {
    if (!selectedSector) {
      setConstituents([]);
      return;
    }

    // Fetch scanner filtered by sector
    const fetchConstituents = async () => {
      try {
        const res = await fetch(
          `/api/proxy/api/v1/scanner?sector=${encodeURIComponent(selectedSector.sector_name)}&limit=10`
        );
        if (res.ok) {
          const data = await res.json();
          const items = (data.items || []).map((item: any) => ({
            symbol: item.symbol,
            name: item.name,
            price_usd: item.price,
            return_24h: item.return_24h,
            opportunity_score: item.opportunity_score,
          }));
          setConstituents(items);
        }
      } catch {
        setConstituents([]);
      }
    };

    fetchConstituents();
  }, [selectedSector]);

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case "LEADING":
        return "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";
      case "ACCELERATING":
        return "bg-sky-500/20 text-sky-300 border-sky-500/30";
      case "WEAKENING":
        return "bg-amber-500/20 text-amber-300 border-amber-500/30";
      default:
        return "bg-rose-500/20 text-rose-300 border-rose-500/30";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-[var(--border-subtle)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              Sector Momentum & Rotation Map
            </h1>
            <span className="text-xs px-2 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/20 font-mono font-medium">
              Capital Cycles
            </span>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Tracking cross-sector relative momentum, 7D market breadth, and capital flow rotation quadrants.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Status Filter */}
          <div className="flex items-center bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-[var(--radius-sm)] p-0.5 text-xs font-mono">
            {(["ALL", "LEADING", "ACCELERATING", "WEAKENING", "DECLINING"] as const).map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-2.5 py-1 rounded-[var(--radius-sm)] transition ${
                  statusFilter === st
                    ? "bg-[var(--bg-card)] text-white font-bold shadow-sm"
                    : "text-[var(--text-dim)] hover:text-white"
                }`}
              >
                {st}
              </button>
            ))}
          </div>

          <button
            onClick={fetchSectors}
            disabled={loading}
            className="p-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-dim)] hover:text-white transition disabled:opacity-50"
            title="Refresh sectors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Rotation Quadrant Scatter Chart */}
      <SectorRotationChart
        sectors={sectors}
        onSelectSector={(s) => setSelectedSector(s)}
      />

      {/* Sector Performance Table */}
      <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] overflow-hidden">
        <div className="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
              Sector Performance Matrix ({sectors.length} Sectors)
            </h3>
            <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
              Multi-horizon returns, breadth expansion, and volume acceleration. Click a row for constituent assets.
            </p>
          </div>
          <span className="text-[10px] font-mono text-[var(--text-dim)]">
            Sorted by 7-Day Performance
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="text-[10px] uppercase text-[var(--text-dim)] bg-[var(--bg-card)]/50 border-b border-[var(--border-subtle)]">
              <tr>
                <th className="py-2.5 px-4 font-semibold">Sector</th>
                <th className="py-2.5 px-3 font-semibold text-center">Assets</th>
                <th className="py-2.5 px-3 font-semibold text-right">1D Return</th>
                <th className="py-2.5 px-3 font-semibold text-right">7D Return</th>
                <th className="py-2.5 px-3 font-semibold text-right">30D Return</th>
                <th className="py-2.5 px-4 font-semibold text-right">Breadth (% Pos)</th>
                <th className="py-2.5 px-4 font-semibold text-right">7D Vol Chg</th>
                <th className="py-2.5 px-4 font-semibold text-center">Rotation Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {sectors.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-[var(--text-dim)]">
                    No sectors matching the selected filter.
                  </td>
                </tr>
              ) : (
                sectors.map((s) => (
                  <tr
                    key={`sec-${s.sector_name}`}
                    onClick={() => setSelectedSector(s)}
                    className={`hover:bg-[var(--bg-card)]/50 transition cursor-pointer ${
                      selectedSector?.sector_name === s.sector_name ? "bg-[var(--bg-card)]/80" : ""
                    }`}
                  >
                    <td className="py-3 px-4 font-bold text-white flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-sky-400" />
                      <span>{s.sector_name}</span>
                    </td>

                    <td className="py-3 px-3 text-center text-[var(--text-secondary)]">
                      {s.asset_count}
                    </td>

                    <td className="py-3 px-3 text-right">
                      <DeltaCell value={s.return_1d * 100} />
                    </td>

                    <td className="py-3 px-3 text-right">
                      <DeltaCell value={s.return_7d * 100} />
                    </td>

                    <td className="py-3 px-3 text-right">
                      <DeltaCell value={s.return_30d * 100} />
                    </td>

                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <span className="font-semibold text-white">
                          {s.breadth_pct.toFixed(0)}%
                        </span>
                        <div className="w-12 h-1.5 bg-black/40 rounded-full overflow-hidden">
                          <div
                            className={`h-full ${
                              s.breadth_pct >= 60 ? "bg-emerald-400" : s.breadth_pct <= 40 ? "bg-rose-400" : "bg-sky-400"
                            }`}
                            style={{ width: `${Math.min(100, Math.max(0, s.breadth_pct))}%` }}
                          />
                        </div>
                      </div>
                    </td>

                    <td className="py-3 px-4 text-right">
                      <DeltaCell value={s.volume_change_7d_pct * 100} />
                    </td>

                    <td className="py-3 px-4 text-center">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold border ${getStatusBadge(
                          s.rotation_status
                        )}`}
                      >
                        {s.rotation_status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Constituent Assets Drill-Down Drawer */}
      {selectedSector && (
        <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-[var(--border-subtle)]">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-sky-400" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
                Constituents in {selectedSector.sector_name} ({selectedSector.asset_count} tracked assets)
              </h3>
            </div>
            <button
              onClick={() => setSelectedSector(null)}
              className="text-xs text-[var(--text-dim)] hover:text-white transition flex items-center gap-1"
            >
              <X className="w-3.5 h-3.5" />
              <span>Dismiss</span>
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 font-mono text-xs">
            {constituents.length === 0 ? (
              <p className="text-[var(--text-dim)] py-2 col-span-4">
                Loading constituent assets for {selectedSector.sector_name}...
              </p>
            ) : (
              constituents.map((item) => (
                <Link
                  key={`const-${item.symbol}`}
                  href={`/assets/${item.symbol}`}
                  className="p-3 rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-card)] hover:border-sky-500/40 transition group flex flex-col justify-between"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-bold text-white group-hover:text-sky-300 transition">
                        {item.symbol}
                      </span>
                      <span className="text-[10px] text-[var(--text-dim)] block truncate max-w-[120px]">
                        {item.name}
                      </span>
                    </div>
                    <ScoreBadge score={item.opportunity_score} size="sm" />
                  </div>

                  <div className="flex items-center justify-between mt-2 pt-2 border-t border-[var(--border-subtle)]">
                    <span className="text-white font-semibold">
                      ${item.price_usd?.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                    </span>
                    <DeltaCell value={item.return_24h * 100} />
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
