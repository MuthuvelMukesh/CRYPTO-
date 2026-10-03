"use client";

import React, { useState } from "react";
import { TrendingUp, ShieldAlert } from "lucide-react";
import { formatPrice, formatPercent, formatUTC, EMPTY_FALLBACK } from "@/lib/format";

export interface EquityPoint {
  time: string;
  equity: number;
  cash?: number;
  drawdown_pct?: number;
}

interface EquityChartProps {
  data: EquityPoint[];
  peakEquity?: number | null;
  startingCapital?: number;
  currentDrawdown?: number | null;
  className?: string;
}

export function EquityChart({
  data,
  peakEquity,
  startingCapital = 100000,
  currentDrawdown = 0,
  className = "",
}: EquityChartProps) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  if (!data || data.length < 2) {
    return (
      <div
        className={`rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center ${className}`}
      >
        <div className="flex items-center justify-between pb-3 mb-2 border-b border-[var(--border-subtle)]">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
              Portfolio Equity Curve
            </h3>
          </div>
          <span className="text-[10px] font-mono text-[var(--text-dim)]">
            Awaiting execution fills
          </span>
        </div>
        <p className="text-xs font-mono text-[var(--text-muted)] py-10">
          Mark-to-market equity curve will plot once execution events are recorded.
        </p>
      </div>
    );
  }

  const points: EquityPoint[] = data;
  const currentEquity = points[points.length - 1]?.equity;
  const netReturnPct =
    startingCapital > 0 && currentEquity !== undefined
      ? ((currentEquity - startingCapital) / startingCapital) * 100
      : 0;
  const isPositive = netReturnPct >= 0;

  // Chart Dimensions
  const width = 700;
  const height = 220;
  const padding = { top: 20, right: 30, bottom: 30, left: 60 };

  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  const minEquity = Math.min(...points.map((p) => p.equity)) * 0.98;
  const maxEquity = Math.max(...points.map((p) => p.equity)) * 1.02;
  const range = maxEquity - minEquity || 1;

  const getX = (idx: number) => padding.left + (idx / (points.length - 1)) * plotWidth;
  const getY = (val: number) => padding.top + plotHeight - ((val - minEquity) / range) * plotHeight;

  // Generate SVG path for line and area fill
  const linePoints = points.map((p, i) => `${getX(i).toFixed(1)},${getY(p.equity).toFixed(1)}`).join(" ");
  const areaPath = `M ${getX(0)},${getY(points[0]!.equity)} ${points
    .map((p, i) => `L ${getX(i).toFixed(1)},${getY(p.equity).toFixed(1)}`)
    .join(" ")} L ${getX(points.length - 1)},${padding.top + plotHeight} L ${getX(0)},${
    padding.top + plotHeight
  } Z`;

  const activePoint = hoverIdx !== null ? points[hoverIdx] : points[points.length - 1];

  return (
    <div
      className={`rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 flex flex-col justify-between ${className}`}
    >
      {/* Chart Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-2 border-b border-[var(--border-subtle)] gap-2">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
              Portfolio Equity Curve
            </h3>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-secondary)]">
            Mark-to-Market Real-Time
          </span>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono">
          <div>
            <span className="text-[10px] text-[var(--text-dim)] uppercase block">
              Net Performance
            </span>
            <span
              className={`font-bold ${
                isPositive ? "text-[var(--color-positive)]" : "text-[var(--color-negative)]"
              }`}
            >
              {isPositive ? "+" : ""}
              {netReturnPct.toFixed(2)}%
            </span>
          </div>

          <div>
            <span className="text-[10px] text-[var(--text-dim)] uppercase block">
              Peak Equity
            </span>
            <span className="font-bold text-white">
              {formatPrice(peakEquity ?? currentEquity)}
            </span>
          </div>

          {currentDrawdown !== undefined && currentDrawdown !== null && (
            <div>
              <span className="text-[10px] text-[var(--text-dim)] uppercase block">
                Current Drawdown
              </span>
              <span
                className={`font-bold ${
                  currentDrawdown > 10 ? "text-rose-400 font-extrabold" : "text-[var(--text-secondary)]"
                }`}
              >
                -{Math.abs(currentDrawdown).toFixed(2)}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* SVG Canvas */}
      <div className="relative w-full overflow-hidden">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-auto overflow-visible select-none"
          role="img"
          aria-label="Portfolio equity curve chart"
        >
          <defs>
            <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.28" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Horizontal Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1.0].map((ratio) => {
            const y = padding.top + plotHeight * (1 - ratio);
            const val = minEquity + range * ratio;
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
                  ${(val / 1000).toFixed(1)}k
                </text>
              </g>
            );
          })}

          {/* Area Fill */}
          <path d={areaPath} fill="url(#equityFill)" />

          {/* Stroke Line */}
          <polyline
            fill="none"
            stroke="#10b981"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={linePoints}
          />

          {/* Interactive Hover Point & Vertical Marker */}
          {hoverIdx !== null && (
            <g>
              <line
                x1={getX(hoverIdx)}
                y1={padding.top}
                x2={getX(hoverIdx)}
                y2={padding.top + plotHeight}
                stroke="#38bdf8"
                strokeWidth="1"
                strokeDasharray="2,2"
              />
              <circle
                cx={getX(hoverIdx)}
                cy={getY(points[hoverIdx]!.equity)}
                r="4.5"
                fill="#38bdf8"
                stroke="#0f172a"
                strokeWidth="2"
              />
            </g>
          )}

          {/* Transparent Hover Area Capture Slices */}
          {points.map((p, i) => (
            <rect
              key={i}
              x={getX(i) - (plotWidth / points.length) / 2}
              y={padding.top}
              width={plotWidth / points.length}
              height={plotHeight}
              fill="transparent"
              className="cursor-crosshair"
              onMouseEnter={() => setHoverIdx(i)}
              onMouseLeave={() => setHoverIdx(null)}
            />
          ))}
        </svg>

        {/* Floating Tooltip Status */}
        {activePoint && (
          <div className="flex items-center justify-between text-[11px] font-mono text-[var(--text-dim)] pt-2 border-t border-[var(--border-subtle)]">
            <span className="text-[var(--text-secondary)]">
              {formatUTC(activePoint.time)}
            </span>
            <div className="flex items-center gap-3">
              <span>
                Equity: <strong className="text-white">{formatPrice(activePoint.equity)}</strong>
              </span>
              {activePoint.cash !== undefined && (
                <span>
                  Cash: <strong className="text-sky-300">{formatPrice(activePoint.cash)}</strong>
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
