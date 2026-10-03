"use client";

import React from "react";
import { formatScore, EMPTY_FALLBACK } from "@/lib/format";

interface FactorRadarChartProps {
  trendScore?: number | null;
  momentumScore?: number | null;
  qualityScore?: number | null;
  liquidityScore?: number | null;
  relativeStrengthScore?: number | null;
  opportunityScore?: number | null;
  className?: string;
}

export function FactorRadarChart({
  trendScore,
  momentumScore,
  qualityScore,
  liquidityScore,
  relativeStrengthScore,
  opportunityScore,
  className = "",
}: FactorRadarChartProps) {
  const factors = [
    { label: "Trend", score: trendScore ?? 0, angle: -90 },
    { label: "Momentum", score: momentumScore ?? 0, angle: -18 },
    { label: "Quality", score: qualityScore ?? 0, angle: 54 },
    { label: "Liquidity", score: liquidityScore ?? 0, angle: 126 },
    { label: "Rel Strength", score: relativeStrengthScore ?? 0, angle: 198 },
  ];

  const size = 260;
  const center = size / 2;
  const radius = 90;

  // Degrees to radians helper
  const toRad = (deg: number) => (deg * Math.PI) / 180;

  // Calculate polygon coordinates for given scale (0 to 1)
  const getPolygonPoints = (scale: number) => {
    return factors
      .map((f) => {
        const rad = toRad(f.angle);
        const x = center + radius * scale * Math.cos(rad);
        const y = center + radius * scale * Math.sin(rad);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  };

  // Calculate points for the actual factor scores
  const scorePoints = factors
    .map((f) => {
      const scale = Math.min(100, Math.max(0, f.score)) / 100;
      const rad = toRad(f.angle);
      const x = center + radius * scale * Math.cos(rad);
      const y = center + radius * scale * Math.sin(rad);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <div
      className={`rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 flex flex-col items-center justify-between ${className}`}
    >
      <div className="w-full flex items-center justify-between pb-2 mb-2 border-b border-[var(--border-subtle)]">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
          Factor Radar Profile
        </h3>
        {opportunityScore !== undefined && opportunityScore !== null && (
          <span className="text-[11px] font-mono text-sky-400 font-bold">
            Net Score: {formatScore(opportunityScore)}
          </span>
        )}
      </div>

      <div className="relative flex items-center justify-center my-2">
        <svg
          width={size}
          height={size}
          className="overflow-visible"
          role="img"
          aria-label="Factor radar visualization"
        >
          {/* Concentric Grid Polygons (20%, 40%, 60%, 80%, 100%) */}
          {[0.2, 0.4, 0.6, 0.8, 1.0].map((ring) => (
            <polygon
              key={ring}
              points={getPolygonPoints(ring)}
              fill="none"
              stroke="#1e293b"
              strokeWidth="1"
              strokeDasharray={ring === 1.0 ? "none" : "2,2"}
            />
          ))}

          {/* Radial Axis Lines */}
          {factors.map((f) => {
            const rad = toRad(f.angle);
            const x2 = center + radius * Math.cos(rad);
            const y2 = center + radius * Math.sin(rad);
            return (
              <line
                key={f.label}
                x1={center}
                y1={center}
                x2={x2}
                y2={y2}
                stroke="#1e293b"
                strokeWidth="1"
              />
            );
          })}

          {/* Score Polygon Fill */}
          <polygon
            points={scorePoints}
            fill="rgba(56, 189, 248, 0.25)"
            stroke="#38bdf8"
            strokeWidth="2"
          />

          {/* Score Vertex Dots */}
          {factors.map((f) => {
            const scale = Math.min(100, Math.max(0, f.score)) / 100;
            const rad = toRad(f.angle);
            const cx = center + radius * scale * Math.cos(rad);
            const cy = center + radius * scale * Math.sin(rad);
            return (
              <circle
                key={f.label}
                cx={cx}
                cy={cy}
                r="3.5"
                fill="#38bdf8"
                stroke="#0f172a"
                strokeWidth="1.5"
              />
            );
          })}

          {/* Perimeter Labels */}
          {factors.map((f) => {
            const rad = toRad(f.angle);
            // Push labels slightly outside the perimeter
            const labelRadius = radius + 22;
            const lx = center + labelRadius * Math.cos(rad);
            const ly = center + labelRadius * Math.sin(rad);
            return (
              <text
                key={f.label}
                x={lx}
                y={ly}
                textAnchor="middle"
                dominantBaseline="central"
                className="fill-[var(--text-secondary)] text-[10px] font-mono font-medium"
              >
                {f.label}
              </text>
            );
          })}
        </svg>
      </div>

      {/* Mini Factor Grid Summary */}
      <div className="w-full grid grid-cols-5 gap-1 pt-2 border-t border-[var(--border-subtle)] text-center">
        {factors.map((f) => (
          <div key={f.label} className="p-1 rounded bg-[var(--bg-card)]">
            <span className="text-[9px] text-[var(--text-dim)] block truncate">
              {f.label.slice(0, 4)}
            </span>
            <span className="text-[11px] font-mono font-bold text-white">
              {f.score ? f.score.toFixed(0) : EMPTY_FALLBACK}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
