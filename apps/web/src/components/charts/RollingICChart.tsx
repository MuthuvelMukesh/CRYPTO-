"use client";

import React, { useState } from "react";
import { formatPercent, EMPTY_FALLBACK } from "@/lib/format";

export interface RollingICPoint {
  date: string;
  pearson_ic: number;
  spearman_ic: number;
  sample_size: number;
}

interface RollingICChartProps {
  points?: RollingICPoint[];
  horizon?: string;
  className?: string;
}

export function RollingICChart({
  points = [],
  horizon = "1d",
  className = "",
}: RollingICChartProps) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  if (!points || points.length === 0) {
    return (
      <div className={`rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center ${className}`}>
        <p className="text-xs text-[var(--text-dim)]">Awaiting Information Coefficient time-series data...</p>
      </div>
    );
  }

  const height = 220;
  const padding = { top: 20, right: 30, bottom: 35, left: 45 };
  const width = 640;

  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;

  // Determine Y range (-0.4 to +0.4 or dynamic clamped to [-1, 1])
  const allICs = points.flatMap((p) => [p.pearson_ic, p.spearman_ic]);
  const minVal = Math.min(-0.1, Math.min(...allICs) - 0.05);
  const maxVal = Math.max(0.25, Math.max(...allICs) + 0.05);
  const ySpan = maxVal - minVal || 0.5;

  const getX = (index: number) => {
    if (points.length <= 1) return padding.left + innerWidth / 2;
    return padding.left + (index / (points.length - 1)) * innerWidth;
  };

  const getY = (val: number) => {
    const ratio = (val - minVal) / ySpan;
    return padding.top + innerHeight - ratio * innerHeight;
  };

  const zeroY = getY(0);
  const alphaThresholdY = getY(0.05);

  const pearsonPath = points
    .map((p, idx) => `${idx === 0 ? "M" : "L"} ${getX(idx).toFixed(1)} ${getY(p.pearson_ic).toFixed(1)}`)
    .join(" ");

  const spearmanPath = points
    .map((p, idx) => `${idx === 0 ? "M" : "L"} ${getX(idx).toFixed(1)} ${getY(p.spearman_ic).toFixed(1)}`)
    .join(" ");

  const hoveredPoint = hoveredIdx !== null ? points[hoveredIdx] : null;

  return (
    <div
      className={`rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 ${className}`}
      role="region"
      aria-label="Information Coefficient Time Series"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-2 border-b border-[var(--border-subtle)] gap-2">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
              Rolling Information Coefficient (IC)
            </h3>
            <span className="text-[10px] px-1.5 py-0.5 rounded font-mono bg-sky-500/10 text-sky-400 border border-sky-500/20">
              Horizon: {horizon.toUpperCase()}
            </span>
          </div>
          <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
            Linear (Pearson) and Monotonic Rank (Spearman) predictive efficacy over time.
          </p>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-0.5 bg-sky-400 inline-block" />
            <span className="text-sky-300">Pearson IC</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-0.5 bg-emerald-400 inline-block" />
            <span className="text-emerald-300">Spearman Rank IC</span>
          </div>
          <div className="flex items-center gap-1.5 text-[var(--text-dim)]">
            <span className="w-2.5 h-0.5 border-b border-dashed border-amber-400/60 inline-block" />
            <span className="text-[10px] text-amber-400/80">Alpha Gate (+0.05)</span>
          </div>
        </div>
      </div>

      <div className="relative">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-auto max-h-[260px] overflow-visible"
          role="img"
          aria-label="Rolling IC Line Chart"
        >
          {/* Grid lines */}
          <line
            x1={padding.left}
            y1={zeroY}
            x2={width - padding.right}
            y2={zeroY}
            stroke="var(--border-subtle)"
            strokeWidth="1.5"
          />
          <text
            x={padding.left - 8}
            y={zeroY + 3}
            textAnchor="end"
            className="text-[10px] fill-[var(--text-dim)] font-mono"
          >
            0.00
          </text>

          {/* Alpha gate line at +0.05 */}
          {alphaThresholdY >= padding.top && alphaThresholdY <= padding.top + innerHeight && (
            <line
              x1={padding.left}
              y1={alphaThresholdY}
              x2={width - padding.right}
              y2={alphaThresholdY}
              stroke="rgba(251, 191, 36, 0.4)"
              strokeDasharray="3 3"
              strokeWidth="1"
            />
          )}

          {/* Pearson path */}
          <path
            d={pearsonPath}
            fill="none"
            stroke="#38bdf8"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Spearman path */}
          <path
            d={spearmanPath}
            fill="none"
            stroke="#34d399"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Data point dots & hover areas */}
          {points.map((p, idx) => {
            const x = getX(idx);
            const yP = getY(p.pearson_ic);
            const yS = getY(p.spearman_ic);
            const isHovered = hoveredIdx === idx;

            return (
              <g key={`pt-${idx}`}>
                {/* Vertical cursor guide */}
                {isHovered && (
                  <line
                    x1={x}
                    y1={padding.top}
                    x2={x}
                    y2={padding.top + innerHeight}
                    stroke="rgba(255,255,255,0.2)"
                    strokeDasharray="2 2"
                    strokeWidth="1"
                  />
                )}

                {/* Pearson point */}
                <circle
                  cx={x}
                  cy={yP}
                  r={isHovered ? 4.5 : 2.5}
                  fill="#38bdf8"
                  className="transition-all"
                />

                {/* Spearman point */}
                <circle
                  cx={x}
                  cy={yS}
                  r={isHovered ? 4.5 : 2.5}
                  fill="#34d399"
                  className="transition-all"
                />

                {/* Invisible hover hotspot */}
                <rect
                  x={x - 12}
                  y={padding.top}
                  width={24}
                  height={innerHeight}
                  fill="transparent"
                  className="cursor-pointer"
                  onMouseEnter={() => setHoveredIdx(idx)}
                  onMouseLeave={() => setHoveredIdx(null)}
                />
              </g>
            );
          })}

          {/* X-axis date labels */}
          {points.map((p, idx) => {
            // Show every few labels to prevent overlap
            const step = Math.max(1, Math.floor(points.length / 6));
            if (idx % step !== 0 && idx !== points.length - 1) return null;
            const x = getX(idx);
            const shortDate = p.date.length > 5 ? p.date.slice(5) : p.date;
            return (
              <text
                key={`lbl-${idx}`}
                x={x}
                y={height - 8}
                textAnchor="middle"
                className="text-[10px] fill-[var(--text-dim)] font-mono"
              >
                {shortDate}
              </text>
            );
          })}
        </svg>

        {/* Hover Tooltip Overlay */}
        {hoveredPoint && hoveredIdx !== null && (
          <div
            className="absolute top-2 pointer-events-none rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-card)]/95 backdrop-blur-md p-2.5 shadow-xl text-xs font-mono z-10"
            style={{
              left: `${Math.min(Math.max(10, (hoveredIdx / (points.length - 1)) * 90), 75)}%`,
            }}
          >
            <div className="font-semibold text-white mb-1 pb-1 border-b border-[var(--border-subtle)]">
              {hoveredPoint.date} (N = {hoveredPoint.sample_size})
            </div>
            <div className="flex items-center justify-between gap-4 text-sky-400">
              <span>Pearson IC:</span>
              <span className="font-bold">
                {hoveredPoint.pearson_ic > 0 ? "+" : ""}
                {hoveredPoint.pearson_ic.toFixed(4)}
              </span>
            </div>
            <div className="flex items-center justify-between gap-4 text-emerald-400">
              <span>Spearman IC:</span>
              <span className="font-bold">
                {hoveredPoint.spearman_ic > 0 ? "+" : ""}
                {hoveredPoint.spearman_ic.toFixed(4)}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
