"use client";

import { useId } from "react";
import { EMPTY_FALLBACK } from "../../lib/format";

interface SparklineProps {
  data: number[] | null | undefined;
  width?: number;
  height?: number;
  strokeWidth?: number;
  className?: string;
}

export function Sparkline({
  data,
  width = 72,
  height = 20,
  strokeWidth = 1.5,
  className = "",
}: SparklineProps) {
  const gradientId = useId();

  if (!data || data.length < 2) {
    return <span className={`font-mono text-xs text-[var(--text-dim)] ${className}`}>{EMPTY_FALLBACK}</span>;
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min === 0 ? 1 : max - min;

  // Add 1px padding to avoid clipping stroke
  const padding = strokeWidth;
  const drawWidth = width - padding * 2;
  const drawHeight = height - padding * 2;

  const points = data.map((val, idx) => {
    const x = padding + (idx / (data.length - 1)) * drawWidth;
    const y = padding + drawHeight - ((val - min) / range) * drawHeight;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const pathD = `M ${points.join(" L ")}`;

  // Close path for area fill
  const firstPoint = points[0] ? points[0].split(",")[0] : `${padding}`;
  const lastPoint = points[points.length - 1] ? points[points.length - 1].split(",")[0] : `${width - padding}`;
  const areaD = `${pathD} L ${lastPoint},${height} L ${firstPoint},${height} Z`;

  const isUp = (data[data.length - 1] ?? 0) >= (data[0] ?? 0);
  const strokeColor = isUp ? "#10b981" : "#f43f5e";
  const fillColor = isUp ? "rgba(16, 185, 129, 0.15)" : "rgba(244, 63, 94, 0.15)";

  const pctChange = (((data[data.length - 1] ?? 0) - (data[0] ?? 0)) / (data[0] || 1)) * 100;
  const tooltip = `7D Trend: ${pctChange > 0 ? "+" : ""}${pctChange.toFixed(2)}%\nMin: ${min.toFixed(2)} | Max: ${max.toFixed(2)}`;

  return (
    <div
      className={`inline-flex items-center justify-center ${className}`}
      title={tooltip}
    >
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="overflow-visible"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={strokeColor} stopOpacity="0.25" />
            <stop offset="100%" stopColor={strokeColor} stopOpacity="0.0" />
          </linearGradient>
        </defs>

        {/* Gradient Area */}
        <path d={areaD} fill={`url(#${gradientId})`} />

        {/* Line Stroke */}
        <path
          d={pathD}
          fill="none"
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}
