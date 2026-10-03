"use client";

import React, { useState, useEffect } from "react";
import {
  Flame,
  ShieldAlert,
  Search,
  Filter,
  RefreshCw,
  ExternalLink,
  AlertTriangle,
  Info,
  Layers,
} from "lucide-react";
import { formatPrice, formatCompactUSD, formatPercent, EMPTY_FALLBACK } from "@/lib/format";
import { ScoreBadge } from "@/components/data";
import { MemeDetailDrawer, MemeDetailData } from "@/components/domain/MemeDetailDrawer";

export default function MemesPage() {
  const [loading, setLoading] = useState(true);
  const [memes, setMemes] = useState<MemeDetailData[]>([]);
  const [selectedMeme, setSelectedMeme] = useState<MemeDetailData | null>(null);

  // Filters
  const [search, setSearch] = useState("");
  const [minScore, setMinScore] = useState<number>(0);
  const [riskFilter, setRiskFilter] = useState<string>("ALL");

  const fetchMemes = async () => {
    setLoading(true);
    try {
      const url = `/api/proxy/api/v1/meme/radar?min_score=${minScore}${
        riskFilter !== "ALL" ? `&max_risk_level=${riskFilter}` : ""
      }`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setMemes(data);
      }
    } catch {
      // Handled via state
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMemes();
  }, [minScore, riskFilter]);

  const filteredMemes = memes.filter((m) => {
    if (search.trim() === "") return true;
    const q = search.toLowerCase();
    return (
      m.symbol.toLowerCase().includes(q) ||
      m.name.toLowerCase().includes(q) ||
      m.chain_id.toLowerCase().includes(q) ||
      m.dex_id.toLowerCase().includes(q)
    );
  });

  const getRiskColor = (level: string) => {
    switch (level.toUpperCase()) {
      case "CRITICAL":
        return "bg-rose-500/20 text-rose-300 border-rose-500/30";
      case "HIGH":
        return "bg-amber-500/20 text-amber-300 border-amber-500/30";
      case "MODERATE":
        return "bg-sky-500/20 text-sky-300 border-sky-500/30";
      default:
        return "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-[var(--border-subtle)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              Meme Coin Radar & DEX Intelligence
            </h1>
            <span className="text-xs px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30 font-mono font-medium">
              Convexity Radar
            </span>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Real-time on-chain liquidity dynamics, volume acceleration bursts, and strict penalty audits for rug hazards.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchMemes}
            disabled={loading}
            className="p-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-dim)] hover:text-white transition disabled:opacity-50"
            title="Refresh meme tokens"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Prominent High-Risk Cautionary Framing Banner */}
      <div className="rounded-[var(--radius-md)] border border-amber-500/40 bg-amber-950/20 p-4 text-xs font-mono text-amber-200 flex items-start gap-3 shadow-lg">
        <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-bold text-amber-300 uppercase tracking-wider block">
            Cautionary High-Risk Warning — DEX Speculative Assets
          </span>
          <p className="text-amber-200/80 leading-relaxed text-[11px]">
            Meme tokens trade on permissionless automated market maker (AMM) pools with extreme price slippage, low liquidity depth, and holder concentration hazards. Every score displayed applies a strict quantitative risk deduction matrix for low pool liquidity, rapid dev dumping, and contract vulnerabilities. Non-custodial research only.
          </p>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="p-3.5 rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-[var(--text-dim)] absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search symbol, pair..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-[var(--radius-sm)] text-xs text-white placeholder-[var(--text-dim)] focus:outline-none focus:border-sky-500 w-44"
            />
          </div>

          {/* Min Score Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-[var(--text-dim)]">Min Score:</span>
            <select
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="px-2 py-1 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-[var(--radius-sm)] text-white focus:outline-none"
            >
              <option value={0}>0 (All)</option>
              <option value={50}>≥ 50 (Fair)</option>
              <option value={70}>≥ 70 (Strong)</option>
              <option value={80}>≥ 80 (Elite)</option>
            </select>
          </div>

          {/* Risk Level Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-[var(--text-dim)]">Max Risk:</span>
            <div className="flex items-center bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-[var(--radius-sm)] p-0.5">
              {(["ALL", "LOW", "MODERATE", "HIGH"] as const).map((lvl) => (
                <button
                  key={lvl}
                  onClick={() => setRiskFilter(lvl)}
                  className={`px-2 py-0.5 rounded-[var(--radius-sm)] transition ${
                    riskFilter === lvl
                      ? "bg-white/10 text-white font-bold"
                      : "text-[var(--text-dim)] hover:text-white"
                  }`}
                >
                  {lvl}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="text-[11px] text-[var(--text-dim)]">
          Showing <span className="text-white font-bold">{filteredMemes.length}</span> tokens
        </div>
      </div>

      {/* Main Meme Radar Table */}
      <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="text-[10px] uppercase text-[var(--text-dim)] bg-[var(--bg-card)]/50 border-b border-[var(--border-subtle)]">
              <tr>
                <th className="py-2.5 px-3.5 font-semibold">Token</th>
                <th className="py-2.5 px-3 font-semibold">Chain / DEX</th>
                <th className="py-2.5 px-3 font-semibold text-right">Price (USD)</th>
                <th className="py-2.5 px-3 font-semibold text-right">Liquidity</th>
                <th className="py-2.5 px-3 font-semibold text-right">24h Vol</th>
                <th className="py-2.5 px-3 font-semibold text-right">Buy Pressure</th>
                <th className="py-2.5 px-3 font-semibold text-right">Top 10 %</th>
                <th className="py-2.5 px-3 font-semibold text-right">Age</th>
                <th className="py-2.5 px-3.5 font-semibold text-center">Score</th>
                <th className="py-2.5 px-3 font-semibold text-center">Risk Level</th>
                <th className="py-2.5 px-3.5 font-semibold">Flags</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {filteredMemes.length === 0 ? (
                <tr>
                  <td colSpan={11} className="py-8 text-center text-[var(--text-dim)]">
                    No meme tokens match current risk and score filter.
                  </td>
                </tr>
              ) : (
                filteredMemes.map((m) => (
                  <tr
                    key={`meme-${m.symbol}-${m.pair_address}`}
                    onClick={() => setSelectedMeme(m)}
                    className="hover:bg-[var(--bg-card)]/50 transition cursor-pointer"
                  >
                    <td className="py-3 px-3.5 font-bold text-white flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-[10px] text-amber-300">
                        {m.symbol.slice(0, 2)}
                      </div>
                      <div>
                        <span className="block">{m.symbol}</span>
                        <span className="text-[10px] text-[var(--text-muted)] font-normal block truncate max-w-[80px]">
                          {m.name}
                        </span>
                      </div>
                    </td>

                    <td className="py-3 px-3 text-[var(--text-secondary)]">
                      <span className="uppercase text-sky-400">{m.chain_id}</span>
                      <span className="text-[var(--text-dim)] block text-[10px] uppercase">
                        {m.dex_id}
                      </span>
                    </td>

                    <td className="py-3 px-3 text-right text-white font-semibold">
                      {formatPrice(m.price_usd)}
                    </td>

                    <td className="py-3 px-3 text-right text-[var(--text-secondary)] font-medium">
                      {formatCompactUSD(m.liquidity_usd)}
                    </td>

                    <td className="py-3 px-3 text-right text-[var(--text-secondary)]">
                      {formatCompactUSD(m.volume_24h_usd)}
                    </td>

                    <td className="py-3 px-3 text-right">
                      <div className="flex flex-col items-end">
                        <span
                          className={`font-bold ${
                            m.buy_pressure_ratio >= 0.55
                              ? "text-emerald-400"
                              : m.buy_pressure_ratio <= 0.45
                              ? "text-rose-400"
                              : "text-white"
                          }`}
                        >
                          {(m.buy_pressure_ratio * 100).toFixed(1)}%
                        </span>
                        <div className="w-12 h-1 bg-black/40 rounded-full mt-1 overflow-hidden">
                          <div
                            className={`h-full ${
                              m.buy_pressure_ratio >= 0.55 ? "bg-emerald-400" : "bg-rose-400"
                            }`}
                            style={{ width: `${Math.min(100, Math.max(0, m.buy_pressure_ratio * 100))}%` }}
                          />
                        </div>
                      </div>
                    </td>

                    <td className="py-3 px-3 text-right">
                      <span
                        className={
                          m.top_10_holders_pct > 60
                            ? "text-rose-400 font-bold"
                            : m.top_10_holders_pct > 40
                            ? "text-amber-400 font-medium"
                            : "text-emerald-400"
                        }
                      >
                        {m.top_10_holders_pct.toFixed(1)}%
                      </span>
                    </td>

                    <td className="py-3 px-3 text-right text-[var(--text-dim)]">
                      {m.pair_age_hours < 24
                        ? `${Math.round(m.pair_age_hours)}h`
                        : `${(m.pair_age_hours / 24).toFixed(0)}d`}
                    </td>

                    <td className="py-3 px-3.5 text-center">
                      <ScoreBadge score={m.opportunity_score} size="sm" />
                    </td>

                    <td className="py-3 px-3 text-center">
                      <span
                        className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-bold border ${getRiskColor(
                          m.risk_level
                        )}`}
                      >
                        {m.risk_level}
                      </span>
                    </td>

                    <td className="py-3 px-3.5">
                      <div className="flex flex-wrap gap-1 max-w-[140px]">
                        {m.risk_flags.length === 0 ? (
                          <span className="text-[10px] text-emerald-400">Clean</span>
                        ) : (
                          m.risk_flags.map((flag, idx) => (
                            <span
                              key={`flag-${idx}`}
                              className="px-1 py-0.2 rounded text-[9px] bg-rose-500/10 text-rose-300 border border-rose-500/20 truncate max-w-[120px]"
                            >
                              {flag.replace(/_/g, " ")}
                            </span>
                          ))
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail Audit Drawer */}
      <MemeDetailDrawer
        meme={selectedMeme}
        isOpen={selectedMeme !== null}
        onClose={() => setSelectedMeme(null)}
      />
    </div>
  );
}
