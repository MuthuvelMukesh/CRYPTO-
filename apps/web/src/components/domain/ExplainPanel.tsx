"use client";

import { useEffect } from "react";
import Link from "next/link";
import {
  X,
  ExternalLink,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Layers,
  Sparkles,
} from "lucide-react";
import { formatPrice, formatRelativeTime, formatScore } from "@/lib/format";
import { ScoreBadge } from "@/components/data/ScoreBadge";
import { RiskChip } from "@/components/data/RiskChip";

export interface FactorContributionData {
  score: number;
  weight: number;
  contribution: number;
}

export interface PenaltyItemData {
  flag: string;
  deduction: number;
  reason: string;
}

export interface ExplainRankingItem {
  symbol: string;
  name: string;
  asset_class: string;
  primary_sector: string;
  price?: number | null;
  candle_time?: string | null;
  opportunity_score?: number | null;
  score_breakdown?: {
    components: Record<string, FactorContributionData>;
    penalties_total?: number;
    raw_composite?: number;
    final_score?: number;
  } | null;
  penalties?: PenaltyItemData[];
  risk_flags?: string[];
  partial_data?: boolean;
  missing_inputs?: string[];
  model_version?: string | null;
}

interface ExplainPanelProps {
  item: ExplainRankingItem | null;
  open: boolean;
  onClose: () => void;
}

export function ExplainPanel({ item, open, onClose }: ExplainPanelProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open || !item) return null;

  const components = item.score_breakdown?.components || {};
  const factorKeys = Object.keys(components);
  const penalties = item.penalties || [];
  const riskFlags = item.risk_flags || [];
  const isPartial = item.partial_data || (item.missing_inputs && item.missing_inputs.length > 0);

  return (
    <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-xs flex justify-end">
      {/* Background click to dismiss */}
      <div className="flex-1" onClick={onClose} aria-hidden="true" />

      {/* Slide-over Drawer Frame */}
      <div className="w-full max-w-md md:max-w-lg bg-[var(--bg-surface)] border-l border-[var(--border-subtle)] h-full flex flex-col shadow-2xl overflow-hidden animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="p-4 border-b border-[var(--border-subtle)] flex items-start justify-between bg-[var(--bg-card)]/50">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-white tracking-tight font-mono">{item.symbol}</h2>
              <span className="text-xs text-[var(--text-muted)] truncate max-w-[160px]">{item.name}</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-semibold uppercase">
                {item.primary_sector}
              </span>
            </div>
            <div className="flex items-center gap-3 mt-1.5 text-xs text-[var(--text-muted)] font-mono">
              <span className="text-white font-semibold">{formatPrice(item.price)}</span>
              <span>&bull;</span>
              <span>Updated: {formatRelativeTime(item.candle_time)}</span>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <Link
              href={`/assets/${item.symbol}`}
              className="p-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-white hover:border-indigo-400 transition"
              title="Open full asset deep-dive"
            >
              <ExternalLink className="w-4 h-4" />
            </Link>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-[var(--radius-sm)] text-[var(--text-muted)] hover:text-white hover:bg-[var(--bg-card)] transition"
              aria-label="Close explain panel"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-5">
          {/* Top Score Summary Card */}
          <div className="p-3.5 rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-card)] flex items-center justify-between">
            <div>
              <span className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block">
                Composite Opportunity Score
              </span>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-2xl font-bold font-mono text-white">
                  {formatScore(item.opportunity_score)}
                </span>
                <span className="text-xs text-[var(--text-dim)] font-mono">/ 100</span>
              </div>
            </div>

            <div className="flex flex-col items-end gap-1">
              <ScoreBadge score={item.opportunity_score} partialData={isPartial} size="lg" />
              <span className="text-[10px] font-mono text-[var(--text-dim)]">
                Model: {item.model_version || "v3.0.0"}
              </span>
            </div>
          </div>

          {/* Partial Data Notice if triggered */}
          {isPartial && (
            <div className="p-3 rounded-[var(--radius-sm)] bg-amber-500/10 border border-amber-500/30 text-xs text-amber-200 space-y-1">
              <div className="flex items-center gap-1.5 font-semibold text-amber-300">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                <span>Partial Data Weight Redistribution</span>
              </div>
              <p className="text-[11px] text-amber-200/90 leading-relaxed">
                Inputs for <strong className="font-mono text-white">[{item.missing_inputs?.join(", ") || "unreported"}]</strong> were missing.
                Active factor weights were dynamically scaled so active weights sum to 100%, avoiding artificial baselines.
              </p>
            </div>
          )}

          {/* Factor Waterfall Breakdown */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-indigo-400" />
                <span>Factor Attribution Waterfall</span>
              </h3>
              <span className="text-[11px] font-mono text-[var(--text-dim)]">Weight &bull; Score &bull; Pts</span>
            </div>

            <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-card)] divide-y divide-[var(--border-subtle)] overflow-hidden">
              {factorKeys.length === 0 ? (
                <div className="p-4 text-center text-xs text-[var(--text-dim)]">
                  Factor breakdown unavailable for this snapshot.
                </div>
              ) : (
                factorKeys.map((key) => {
                  const comp = components[key];
                  if (!comp) return null;

                  const weightPct = Math.round(comp.weight * 100);
                  const displayKey = key.replace(/_/g, " ");

                  return (
                    <div key={key} className="p-2.5 text-xs">
                      <div className="flex items-center justify-between font-mono">
                        <span className="font-medium text-white capitalize">{displayKey}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-[var(--text-dim)]">{weightPct}%</span>
                          <span className="text-[var(--text-secondary)]">{comp.score.toFixed(1)}</span>
                          <span className="text-emerald-400 font-semibold w-12 text-right">
                            +{comp.contribution.toFixed(1)}
                          </span>
                        </div>
                      </div>

                      {/* Mini visual contribution bar */}
                      <div className="mt-1.5 w-full h-1 bg-[var(--bg-surface)] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-indigo-500 rounded-full"
                          style={{ width: `${Math.min(100, comp.score)}%` }}
                        />
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Risk Penalties & Flags Matrix */}
          <div>
            <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
              <span>Risk Flags & Penalties</span>
            </h3>

            {penalties.length === 0 && riskFlags.length === 0 ? (
              <div className="p-3 rounded-[var(--radius-sm)] border border-emerald-500/20 bg-emerald-500/5 text-xs text-emerald-300 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Clean Risk Profile — No penalty deductions applied to this asset.</span>
              </div>
            ) : (
              <div className="space-y-2">
                {/* Active Risk Flag Chips */}
                {riskFlags.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {riskFlags.map((flag) => (
                      <RiskChip key={flag} flag={flag} />
                    ))}
                  </div>
                )}

                {/* Specific Deductions */}
                {penalties.map((pen, idx) => (
                  <div
                    key={`${pen.flag}-${idx}`}
                    className="p-2.5 rounded-[var(--radius-sm)] border border-rose-500/30 bg-rose-500/10 text-xs space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-rose-300 font-mono">{pen.flag}</span>
                      <span className="font-bold text-rose-400 font-mono">
                        {pen.deduction.toFixed(1)} pts
                      </span>
                    </div>
                    <p className="text-[11px] text-rose-200/80 leading-snug">{pen.reason}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer Link */}
        <div className="p-3 border-t border-[var(--border-subtle)] bg-[var(--bg-card)]/40 flex items-center justify-between">
          <span className="text-[11px] text-[var(--text-dim)] font-mono">
            Asset Class: {item.asset_class}
          </span>
          <Link
            href={`/assets/${item.symbol}`}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition"
          >
            <span>Launch Deep-Dive</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    </div>
  );
}
