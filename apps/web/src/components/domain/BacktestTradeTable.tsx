"use client";

import React, { useState, useMemo } from "react";
import { AlertCircle, ArrowUpDown, ExternalLink } from "lucide-react";
import { formatPrice, formatPercent, formatRelativeTime, formatUTC, EMPTY_FALLBACK } from "@/lib/format";
import { DeltaCell } from "@/components/data";

export interface BacktestTrade {
  trade_id?: string;
  id?: string;
  asset_id: string;
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  pnl_usd: number;
  pnl_pct: number;
  fees_usd?: number;
  low_confidence?: boolean;
}

interface BacktestTradeTableProps {
  trades: BacktestTrade[];
  onSelectTrade?: (trade: BacktestTrade) => void;
  className?: string;
}

export function BacktestTradeTable({
  trades = [],
  onSelectTrade,
  className = "",
}: BacktestTradeTableProps) {
  const [sortKey, setSortKey] = useState<keyof BacktestTrade>("entry_time");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [filterSymbol, setFilterSymbol] = useState<string>("ALL");

  const symbols = useMemo(() => {
    const set = new Set<string>();
    for (const t of trades) {
      if (t.asset_id) set.add(t.asset_id);
    }
    return ["ALL", ...Array.from(set).sort()];
  }, [trades]);

  const sortedTrades = useMemo(() => {
    let list = [...trades];
    if (filterSymbol !== "ALL") {
      list = list.filter((t) => t.asset_id === filterSymbol);
    }

    list.sort((a, b) => {
      const aVal = a[sortKey] ?? 0;
      const bVal = b[sortKey] ?? 0;
      if (aVal < bVal) return sortOrder === "asc" ? -1 : 1;
      if (aVal > bVal) return sortOrder === "asc" ? 1 : -1;
      return 0;
    });

    return list;
  }, [trades, filterSymbol, sortKey, sortOrder]);

  const toggleSort = (key: keyof BacktestTrade) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortOrder("desc");
    }
  };

  return (
    <div
      className={`rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 flex flex-col ${className}`}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-3 border-b border-[var(--border-subtle)] gap-2">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
            Simulated Trade Log ({trades.length} fills)
          </h3>
          <p className="text-[11px] text-[var(--text-muted)]">
            Click any row to inspect execution entry/exit markers.
          </p>
        </div>

        {/* Filter by symbol */}
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-[var(--text-dim)]">Asset:</span>
          <select
            value={filterSymbol}
            onChange={(e) => setFilterSymbol(e.target.value)}
            className="px-2 py-1 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-white text-xs focus:outline-hidden"
          >
            {symbols.map((sym) => (
              <option key={sym} value={sym}>
                {sym}
              </option>
            ))}
          </select>
        </div>
      </div>

      {sortedTrades.length === 0 ? (
        <div className="py-8 text-center text-xs font-mono text-[var(--text-dim)]">
          No trade records match current criteria.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-[var(--bg-card)] text-[10px] uppercase text-[var(--text-dim)] border-b border-[var(--border-subtle)] select-none">
              <tr>
                <th className="py-2.5 px-3 font-semibold cursor-pointer" onClick={() => toggleSort("asset_id")}>
                  <div className="flex items-center gap-1">
                    <span>Asset</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="py-2.5 px-3 font-semibold cursor-pointer" onClick={() => toggleSort("entry_time")}>
                  <div className="flex items-center gap-1">
                    <span>Entry Time</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="py-2.5 px-3 font-semibold text-right">Entry Price</th>
                <th className="py-2.5 px-3 font-semibold text-right">Exit Price</th>
                <th className="py-2.5 px-3 font-semibold text-right cursor-pointer" onClick={() => toggleSort("pnl_usd")}>
                  <div className="flex items-center justify-end gap-1">
                    <span>PnL ($)</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="py-2.5 px-3 font-semibold text-right cursor-pointer" onClick={() => toggleSort("pnl_pct")}>
                  <div className="flex items-center justify-end gap-1">
                    <span>PnL (%)</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="py-2.5 px-3 font-semibold text-right">Fees</th>
                <th className="py-2.5 px-3 font-semibold text-center">Flags</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {sortedTrades.map((t, idx) => {
                const id = t.trade_id || t.id || `trade-${idx}`;
                return (
                  <tr
                    key={id}
                    onClick={() => onSelectTrade?.(t)}
                    className="hover:bg-[var(--bg-card)]/50 transition cursor-pointer"
                  >
                    <td className="py-2.5 px-3 font-bold text-white flex items-center gap-1.5">
                      <span>{t.asset_id}</span>
                    </td>
                    <td className="py-2.5 px-3 text-[var(--text-secondary)]">
                      {formatRelativeTime(t.entry_time)}
                    </td>
                    <td className="py-2.5 px-3 text-right text-[var(--text-secondary)]">
                      {formatPrice(t.entry_price)}
                    </td>
                    <td className="py-2.5 px-3 text-right text-white font-semibold">
                      {formatPrice(t.exit_price)}
                    </td>
                    <td className="py-2.5 px-3 text-right font-bold">
                      <span className={t.pnl_usd >= 0 ? "text-emerald-400" : "text-rose-400"}>
                        {t.pnl_usd >= 0 ? "+" : ""}
                        {formatPrice(t.pnl_usd)}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <DeltaCell value={t.pnl_pct} isFraction={false} />
                    </td>
                    <td className="py-2.5 px-3 text-right text-[var(--text-dim)]">
                      ${t.fees_usd?.toFixed(2) || "0.00"}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      {t.low_confidence && (
                        <span
                          className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded text-[9px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30"
                          title="Low confidence trade: fill executed with interpolated spread or estimated volume"
                        >
                          <AlertCircle className="w-2.5 h-2.5" />
                          LOW_CONF
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
