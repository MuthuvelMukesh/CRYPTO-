"use client";

import React, { useState } from "react";
import {
  X,
  ExternalLink,
  Copy,
  Check,
  AlertTriangle,
  Flame,
  ShieldAlert,
  Percent,
  TrendingUp,
  Droplets,
  Users,
} from "lucide-react";
import { formatPrice, formatCompactUSD, formatPercent, EMPTY_FALLBACK } from "@/lib/format";
import { ScoreBadge } from "@/components/data";

export interface MemePenalty {
  rule: string;
  deduction: number;
  reason: string;
}

export interface MemeDetailData {
  symbol: string;
  name: string;
  chain_id: string;
  dex_id: string;
  pair_address: string;
  price_usd: number;
  liquidity_usd: number;
  volume_24h_usd: number;
  volume_acceleration_1h: number;
  volume_acceleration_5m: number;
  buy_pressure_ratio: number;
  pair_age_hours: number;
  top_10_holders_pct: number;
  holder_count: number;
  liquidity_score: number;
  volume_momentum_score: number;
  buy_pressure_score: number;
  holder_distribution_score: number;
  gross_score: number;
  total_penalties: number;
  opportunity_score: number;
  risk_level: string;
  risk_flags: string[];
  penalties_breakdown: MemePenalty[];
}

interface MemeDetailDrawerProps {
  meme: MemeDetailData | null;
  isOpen: boolean;
  onClose: () => void;
}

export function MemeDetailDrawer({ meme, isOpen, onClose }: MemeDetailDrawerProps) {
  const [copied, setCopied] = useState(false);

  if (!isOpen || !meme) return null;

  const handleCopy = () => {
    if (meme.pair_address) {
      navigator.clipboard.writeText(meme.pair_address);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const getRiskColor = (level: string) => {
    switch (level.toUpperCase()) {
      case "CRITICAL":
        return "bg-rose-500/20 text-rose-300 border-rose-500/40";
      case "HIGH":
        return "bg-amber-500/20 text-amber-300 border-amber-500/40";
      case "MODERATE":
        return "bg-sky-500/20 text-sky-300 border-sky-500/40";
      default:
        return "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
    }
  };

  const explorerUrl =
    meme.chain_id.toLowerCase() === "solana"
      ? `https://solscan.io/account/${meme.pair_address}`
      : `https://etherscan.io/address/${meme.pair_address}`;

  return (
    <div
      className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-sm flex justify-end transition-opacity"
      role="dialog"
      aria-modal="true"
      aria-label={`Meme Token Risk Audit: ${meme.symbol}`}
    >
      <div className="w-full max-w-xl bg-[var(--bg-surface)] border-l border-[var(--border-subtle)] h-full overflow-y-auto flex flex-col shadow-2xl animate-in slide-in-from-right duration-200">
        {/* Drawer Header */}
        <div className="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between sticky top-0 bg-[var(--bg-surface)]/95 backdrop-blur-md z-10">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-amber-500/30 to-orange-500/30 border border-amber-500/40 flex items-center justify-center font-bold text-amber-300">
              {meme.symbol.slice(0, 3)}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white">{meme.symbol}</h2>
                <span className="text-xs text-[var(--text-muted)]">{meme.name}</span>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-bold border ${getRiskColor(
                    meme.risk_level
                  )}`}
                >
                  {meme.risk_level} RISK
                </span>
              </div>
              <div className="flex items-center gap-2 text-[10px] font-mono text-[var(--text-dim)] mt-0.5">
                <span className="uppercase text-sky-400">{meme.chain_id}</span>
                <span>•</span>
                <span className="uppercase">{meme.dex_id}</span>
                <span>•</span>
                <span>Age: {meme.pair_age_hours < 24 ? `${Math.round(meme.pair_age_hours)}h` : `${(meme.pair_age_hours / 24).toFixed(1)}d`}</span>
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-[var(--radius-sm)] text-[var(--text-dim)] hover:text-white hover:bg-[var(--bg-card)] transition"
            aria-label="Close drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Drawer Body */}
        <div className="p-5 space-y-6 flex-1 text-xs font-mono">
          {/* Top Quick Metrics */}
          <div className="grid grid-cols-3 gap-2.5">
            <div className="p-3 rounded bg-[var(--bg-card)] border border-[var(--border-subtle)]">
              <span className="text-[10px] text-[var(--text-dim)] block uppercase">Price (DEX)</span>
              <span className="text-sm font-bold text-white block mt-0.5">
                {formatPrice(meme.price_usd)}
              </span>
            </div>
            <div className="p-3 rounded bg-[var(--bg-card)] border border-[var(--border-subtle)]">
              <span className="text-[10px] text-[var(--text-dim)] block uppercase">Liquidity Pool</span>
              <span className="text-sm font-bold text-white block mt-0.5">
                {formatCompactUSD(meme.liquidity_usd)}
              </span>
            </div>
            <div className="p-3 rounded bg-[var(--bg-card)] border border-[var(--border-subtle)]">
              <span className="text-[10px] text-[var(--text-dim)] block uppercase">24h Volume</span>
              <span className="text-sm font-bold text-white block mt-0.5">
                {formatCompactUSD(meme.volume_24h_usd)}
              </span>
            </div>
          </div>

          {/* Opportunity vs Gross Score Waterfall Strip */}
          <div className="p-4 rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-card)]">
            <div className="flex items-center justify-between pb-2 mb-3 border-b border-[var(--border-subtle)]">
              <span className="text-xs font-semibold text-white uppercase tracking-wider">
                Score Penalty Waterfall
              </span>
              <ScoreBadge score={meme.opportunity_score} size="md" />
            </div>

            <div className="grid grid-cols-3 gap-2 text-center py-1">
              <div className="p-2 rounded bg-black/30">
                <span className="text-[10px] text-white/60 block">Gross Score</span>
                <span className="text-base font-bold text-sky-400">
                  {meme.gross_score.toFixed(1)}
                </span>
              </div>
              <div className="p-2 rounded bg-black/30">
                <span className="text-[10px] text-white/60 block">Penalties Deducted</span>
                <span className="text-base font-bold text-rose-400">
                  -{meme.total_penalties.toFixed(1)}
                </span>
              </div>
              <div className="p-2 rounded bg-black/30 border border-emerald-500/30">
                <span className="text-[10px] text-emerald-400 block font-bold">Net Score</span>
                <span className="text-base font-bold text-emerald-300">
                  {meme.opportunity_score.toFixed(1)}
                </span>
              </div>
            </div>
          </div>

          {/* Sub-factor Breakdown Progress Bars */}
          <div className="space-y-3 p-4 rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-card)]">
            <h3 className="text-xs font-semibold text-white uppercase tracking-wider mb-2">
              DEX Microstructure Sub-Scores
            </h3>

            <div>
              <div className="flex justify-between text-[11px] mb-1">
                <span className="text-[var(--text-secondary)] flex items-center gap-1.5">
                  <Droplets className="w-3.5 h-3.5 text-sky-400" />
                  Pool Liquidity Health (25%)
                </span>
                <span className="text-white font-bold">{meme.liquidity_score.toFixed(1)} / 100</span>
              </div>
              <div className="w-full h-1.5 bg-black/50 rounded-full overflow-hidden">
                <div
                  className="h-full bg-sky-400 rounded-full"
                  style={{ width: `${Math.min(100, Math.max(0, meme.liquidity_score))}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-[11px] mb-1">
                <span className="text-[var(--text-secondary)] flex items-center gap-1.5">
                  <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
                  Volume Acceleration (35%)
                </span>
                <span className="text-white font-bold">{meme.volume_momentum_score.toFixed(1)} / 100</span>
              </div>
              <div className="w-full h-1.5 bg-black/50 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-400 rounded-full"
                  style={{ width: `${Math.min(100, Math.max(0, meme.volume_momentum_score))}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-[11px] mb-1">
                <span className="text-[var(--text-secondary)] flex items-center gap-1.5">
                  <Percent className="w-3.5 h-3.5 text-amber-400" />
                  Buy Pressure Dynamics (25%)
                </span>
                <span className="text-white font-bold">{meme.buy_pressure_score.toFixed(1)} / 100</span>
              </div>
              <div className="w-full h-1.5 bg-black/50 rounded-full overflow-hidden">
                <div
                  className="h-full bg-amber-400 rounded-full"
                  style={{ width: `${Math.min(100, Math.max(0, meme.buy_pressure_score))}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-[11px] mb-1">
                <span className="text-[var(--text-secondary)] flex items-center gap-1.5">
                  <Users className="w-3.5 h-3.5 text-indigo-400" />
                  Holder Dispersion (15%)
                </span>
                <span className="text-white font-bold">{meme.holder_distribution_score.toFixed(1)} / 100</span>
              </div>
              <div className="w-full h-1.5 bg-black/50 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-400 rounded-full"
                  style={{ width: `${Math.min(100, Math.max(0, meme.holder_distribution_score))}%` }}
                />
              </div>
            </div>
          </div>

          {/* Active Penalties Matrix */}
          <div className="space-y-2 p-4 rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-card)]">
            <div className="flex items-center gap-2 pb-2 border-b border-[var(--border-subtle)]">
              <ShieldAlert className="w-4 h-4 text-rose-400" />
              <h3 className="text-xs font-semibold text-white uppercase tracking-wider">
                Risk Penalty Audit Matrix ({meme.penalties_breakdown.length} deductions)
              </h3>
            </div>

            {meme.penalties_breakdown.length === 0 ? (
              <p className="text-emerald-400 text-xs py-2">
                ✓ No active risk penalties triggered for this liquidity pool.
              </p>
            ) : (
              <div className="space-y-2 pt-1">
                {meme.penalties_breakdown.map((p, idx) => (
                  <div
                    key={`pen-${idx}`}
                    className="p-2.5 rounded bg-rose-950/20 border border-rose-500/20 text-rose-300 flex items-start justify-between gap-2"
                  >
                    <div>
                      <span className="font-bold block text-[11px] text-white">
                        {p.rule}
                      </span>
                      <span className="text-[10px] text-rose-200/80 leading-normal">
                        {p.reason}
                      </span>
                    </div>
                    <span className="font-bold text-rose-400 text-xs shrink-0">
                      -{p.deduction.toFixed(0)} pts
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Holder & Address Info */}
          <div className="p-4 rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-card)] space-y-2">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-[var(--text-dim)]">Top 10 Holder Concentration:</span>
              <span
                className={`font-bold ${
                  meme.top_10_holders_pct > 60
                    ? "text-rose-400"
                    : meme.top_10_holders_pct > 40
                    ? "text-amber-400"
                    : "text-emerald-400"
                }`}
              >
                {meme.top_10_holders_pct.toFixed(1)}%
              </span>
            </div>

            <div className="flex items-center justify-between text-[11px]">
              <span className="text-[var(--text-dim)]">Total Verified Holders:</span>
              <span className="font-bold text-white">
                {meme.holder_count.toLocaleString()}
              </span>
            </div>

            <div className="flex items-center justify-between text-[11px] pt-2 border-t border-[var(--border-subtle)]">
              <span className="text-[var(--text-dim)]">Pair Contract Address:</span>
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] text-sky-400 font-mono truncate max-w-[180px]">
                  {meme.pair_address}
                </span>
                <button
                  onClick={handleCopy}
                  className="p-1 hover:text-white text-[var(--text-dim)] transition"
                  title="Copy contract address"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
                <a
                  href={explorerUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="p-1 hover:text-white text-[var(--text-dim)] transition"
                  title="Open in Block Explorer"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>
          </div>
        </div>

        {/* Drawer Footer */}
        <div className="p-4 border-t border-[var(--border-subtle)] bg-[var(--bg-surface)] sticky bottom-0 flex items-center justify-between">
          <span className="text-[10px] text-[var(--text-dim)] font-mono">
            Platform Invariant: Paper Simulation Only
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-white text-xs font-semibold hover:bg-white/10 transition"
          >
            Close Audit
          </button>
        </div>
      </div>
    </div>
  );
}
