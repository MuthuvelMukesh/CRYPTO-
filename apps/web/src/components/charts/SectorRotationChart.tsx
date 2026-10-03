"use client";

import React, { useState } from "react";
import { formatPercent } from "@/lib/format";

export interface SectorItem {
  sector_name: string;
  asset_count: number;
  return_1d: number;
  return_7d: number;
  return_30d: number;
  breadth_pct: number;
  volume_change_7d_pct: number;
  rotation_status: string;
}

interface SectorRotationChartProps {
  sectors?: SectorItem[];
  onSelectSector?: (sector: SectorItem) => void;
  className?: string;
}

export function SectorRotationChart({
  sectors = [],
  onSelectSector,
  className = "",
}: SectorRotationChartProps) {
  const [hoveredSector, setHoveredSector] = useState<SectorItem | null>(null);

  if (!sectors || sectors.length === 0) {
    return (
      <div className={`rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center ${className}`}>
        <p className="text-xs text-[var(--text-dim)]">Awaiting sector rotation telemetry...</p>
      </div>
    );
  }

  const width = 500;
  const height = 280;
  const padding = 35;
  const innerWidth = width - padding * 2;
  const innerHeight = height - padding * 2;

  // X axis: 7D return (-20% to +30%)
  // Y axis: Breadth % (0% to 100%)
  const minX = -0.2;
  const maxX = 0.3;
  const rangeX = maxX - minX;

  const getX = (ret7d: number) => {
    const clamped = Math.max(minX, Math.min(maxX, ret7d));
    return padding + ((clamped - minX) / rangeX) * innerWidth;
  };

  const getY = (breadth: number) => {
    const clamped = Math.max(0, Math.min(100, breadth));
    return height - padding - (clamped / 100) * innerHeight;
  };

  const zeroX = getX(0);
  const midY = getY(50);

  const getStatusColor = (status: string) => {
    switch (status.toUpperCase()) {
      case "LEADING":
        return "#34d399"; // emerald
      case "ACCELERATING":
        return "#38bdf8"; // sky
      case "WEAKENING":
        return "#fbbf24"; // amber
      default:
        return "#f43f5e"; // rose
    }
  };

  return (
    <div
      className={`rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 ${className}`}
      role="region"
      aria-label="Sector Capital Rotation Quadrant Map"
    >
      <div className="flex items-center justify-between pb-2 mb-3 border-b border-[var(--border-subtle)]">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
            Sector Rotation Quadrants (7D Return vs Breadth)
          </h3>
          <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
            Cross-sector capital momentum tracking leading, accelerating, weakening, and declining clusters.
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs font-mono">
          <span className="flex items-center gap-1 text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            Leading
          </span>
          <span className="flex items-center gap-1 text-sky-400">
            <span className="w-2 h-2 rounded-full bg-sky-400" />
            Accelerating
          </span>
          <span className="flex items-center gap-1 text-amber-400">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            Weakening
          </span>
          <span className="flex items-center gap-1 text-rose-400">
            <span className="w-2 h-2 rounded-full bg-rose-400" />
            Declining
          </span>
        </div>
      </div>

      <div className="relative">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-auto max-h-[300px] overflow-visible font-mono"
          role="img"
          aria-label="Sector rotation scatter chart"
        >
          {/* Quadrant background labels */}
          <text
            x={padding + 10}
            y={padding + 18}
            className="text-[9px] fill-sky-400/40 font-bold uppercase tracking-wider"
          >
            Accelerating
          </text>
          <text
            x={width - padding - 10}
            y={padding + 18}
            textAnchor="end"
            className="text-[9px] fill-emerald-400/40 font-bold uppercase tracking-wider"
          >
            Leading
          </text>
          <text
            x={padding + 10}
            y={height - padding - 10}
            className="text-[9px] fill-rose-400/40 font-bold uppercase tracking-wider"
          >
            Declining
          </text>
          <text
            x={width - padding - 10}
            y={height - padding - 10}
            textAnchor="end"
            className="text-[9px] fill-amber-400/40 font-bold uppercase tracking-wider"
          >
            Weakening
          </text>

          {/* Quadrant dividing crosshairs */}
          <line
            x1={zeroX}
            y1={padding}
            x2={zeroX}
            y2={height - padding}
            stroke="var(--border-subtle)"
            strokeDasharray="3 3"
            strokeWidth="1.5"
          />
          <line
            x1={padding}
            y1={midY}
            x2={width - padding}
            y2={midY}
            stroke="var(--border-subtle)"
            strokeDasharray="3 3"
            strokeWidth="1.5"
          />

          {/* Axis Labels */}
          <text
            x={width / 2}
            y={height - 8}
            textAnchor="middle"
            className="text-[9px] fill-[var(--text-dim)]"
          >
            7-Day Trailing Return
          </text>
          <text
            x={10}
            y={height / 2}
            textAnchor="middle"
            transform={`rotate(-90 10 ${height / 2})`}
            className="text-[9px] fill-[var(--text-dim)]"
          >
            Breadth (% Positive)
          </text>

          {/* Sector Nodes */}
          {sectors.map((s) => {
            const cx = getX(s.return_7d);
            const cy = getY(s.breadth_pct);
            const color = getStatusColor(s.rotation_status);
            const isHovered = hoveredSector?.sector_name === s.sector_name;

            return (
              <g
                key={`sec-node-${s.sector_name}`}
                className="cursor-pointer transition-all"
                onMouseEnter={() => setHoveredSector(s)}
                onMouseLeave={() => setHoveredSector(null)}
                onClick={() => onSelectSector && onSelectSector(s)}
              >
                {/* Node halo on hover */}
                {isHovered && (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={12}
                    fill={color}
                    opacity={0.25}
                  />
                )}

                {/* Node point */}
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 6 : 4.5}
                  fill={color}
                  stroke="var(--bg-surface)"
                  strokeWidth="1.5"
                />

                {/* Sector Name Tag */}
                <text
                  x={cx}
                  y={cy - 8}
                  textAnchor="middle"
                  className={`text-[10px] font-bold transition-all ${
                    isHovered ? "fill-white" : "fill-[var(--text-secondary)]"
                  }`}
                >
                  {s.sector_name}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Hover Tooltip Overlay */}
        {hoveredSector && (
          <div className="absolute top-2 right-2 pointer-events-none rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-card)]/95 backdrop-blur-md p-3 shadow-xl text-xs font-mono z-10 space-y-1">
            <div className="font-bold text-white border-b border-[var(--border-subtle)] pb-1 mb-1">
              {hoveredSector.sector_name} ({hoveredSector.asset_count} assets)
            </div>
            <div className="flex items-center justify-between gap-4 text-[var(--text-secondary)]">
              <span>7D Return:</span>
              <span className={hoveredSector.return_7d >= 0 ? "text-emerald-400" : "text-rose-400"}>
                {formatPercent(hoveredSector.return_7d, { isFraction: true })}
              </span>
            </div>
            <div className="flex items-center justify-between gap-4 text-[var(--text-secondary)]">
              <span>Breadth:</span>
              <span className="text-white font-bold">{hoveredSector.breadth_pct.toFixed(0)}%</span>
            </div>
            <div className="flex items-center justify-between gap-4 text-[var(--text-secondary)]">
              <span>Status:</span>
              <span style={{ color: getStatusColor(hoveredSector.rotation_status) }} className="font-bold">
                {hoveredSector.rotation_status}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
