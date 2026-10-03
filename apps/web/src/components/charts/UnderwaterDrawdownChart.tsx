"use client";

import React, { useState } from "react";
import { TrendingDown } from "lucide-react";
import { formatPercent, formatUTC, EMPTY_FALLBACK } from "@/lib/format";

export interface DrawdownPoint {
  time: string;
  drawdown_pct: number; // e.g. -4.5 for -4.5%
}

interface UnderwaterDrawdownChartProps {
  data: DrawdownPoint[];
  maxDrawdown?: number | null;
  className?: string;
}

export function UnderwaterDrawdownChart({
  data,
  maxDrawdown,
  className = "",
}: UnderwaterDrawdownChartProps) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  if (!data || data.length < 2) {
    return (
      <div
        className={`rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center ${className}`}
      >
        <div className="flex items-center justify-between pb-3 mb-2 border-b border-[var(--border-subtle)]">
          <div className="flex items-center gap-2">
            <TrendingDown className="w-4 h-4 text-rose-400" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
              Underwater Drawdown Profile
            </h3>
          </div>
          <span className="text-[10px] font-mono text-[var(--text-dim)]">
            Awaiting data
          </span>
        </div>
        <p className="text-xs font-mono text-[var(--text-muted)] py-8">
          Underwater curve will plot once backtest simulation executes.
        </p>
      </div>
    );
  }

  const width = 700;
  const height = 180;
  const padding = { top: 15, right: 30, bottom: 25, left: 55 };

  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  // Drawdowns are <= 0
  const deepest = Math.min(
    -1,
    maxDrawdown ? -Math.abs(maxDrawdown) : Math.min(...data.map((d) => d.drawdown_pct))
  );

  const getX = (idx: number) => padding.left + (idx / (data.length - 1)) * plotWidth;
  // 0% is at top (padding.top), deepest is at bottom (padding.top + plotHeight)
  const getY = (val: number) => {
    const ratio = Math.max(0, Math.min(1, Math.abs(val) / Math.abs(deepest)));
    return padding.top + ratio * plotHeight;
  };

  const linePoints = data
    .map((p, i) => `${getX(i).toFixed(1)},${getY(p.drawdown_pct).toFixed(1)}`)
    .join(" ");

  const areaPath = `M ${getX(0)},${padding.top} ${data
    .map((p, i) => `L ${getX(i).toFixed(1)},${getY(p.drawdown_pct).toFixed(1)}`)
    .join(" ")} L ${getX(data.length - 1)},${padding.top} Z`;

  const activePoint = hoverIdx !== null ? data[hoverIdx] : data[data.length - 1];

  return (
    <div
      className={`rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 flex flex-col justify-between ${className}`}
    >
      <div className="flex items-center justify-between pb-3 mb-2 border-b border-[var(--border-subtle)]">
        <div className="flex items-center gap-2">
          <TrendingDown className="w-4 h-4 text-rose-400" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
            Underwater Drawdown Profile
          </h3>
        </div>

        <div className="flex items-center gap-3 text-xs font-mono">
          <span className="text-[10px] text-[var(--text-dim)] uppercase">Max Drawdown:</span>
          <span className="font-bold text-rose-400">
            {maxDrawdown !== undefined && maxDrawdown !== null
              ? `-${Math.abs(maxDrawdown).toFixed(2)}%`
              : `${deepest.toFixed(2)}%`}
          </span>
        </div>
      </div>

      <div className="relative w-full overflow-hidden">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-auto overflow-visible select-none"
          role="img"
          aria-label="Underwater drawdown chart"
        >
          <defs>
            <linearGradient id="drawdownFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.05" />
              <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.35" />
            </linearGradient>
          </defs>

          {/* Grid lines: 0%, 50%, 100% of deepest drawdown */}
          {[0, 0.5, 1.0].map((ratio) => {
            const y = padding.top + plotHeight * ratio;
            const val = deepest * ratio;
            return (
              <g key={ratio}>
                <line
                  x1={padding.left}
                  y1={y}
                  x2={width - padding.right}
                  y2={y}
                  stroke="#1e293b"
                  strokeWidth="1"
                  strokeDasharray="3,3"
                />
                <text
                  x={padding.left - 8}
                  y={y + 3}
                  textAnchor="end"
                  className="fill-[var(--text-dim)] text-[9px] font-mono"
                >
                  {val.toFixed(1)}%
                </text>
              </g>
            );
          })}

          {/* Area Fill */}
          <path d={areaPath} fill="url(#drawdownFill)" />

          {/* Underwater Line */}
          <polyline
            fill="none"
            stroke="#f43f5e"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={linePoints}
          />

          {/* Hover slice capture */}
          {data.map((p, i) => (
            <rect
              key={i}
              x={getX(i) - (plotWidth / data.length) / 2}
              y={padding.top}
              width={plotWidth / data.length}
              height={plotHeight}
              fill="transparent"
              className="cursor-crosshair"
              onMouseEnter={() => setHoverIdx(i)}
              onMouseLeave={() => setHoverIdx(null)}
            />
          ))}
        </svg>

        {activePoint && (
          <div className="flex items-center justify-between text-[11px] font-mono text-[var(--text-dim)] pt-2 border-t border-[var(--border-subtle)]">
            <span className="text-[var(--text-secondary)]">
              {formatUTC(activePoint.time)}
            </span>
            <span className="text-rose-400 font-bold">
              Drawdown: {activePoint.drawdown_pct.toFixed(2)}%
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
