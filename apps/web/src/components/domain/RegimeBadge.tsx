"use client";

import React from "react";
import { TrendingUp, TrendingDown, Minus, ShieldAlert } from "lucide-react";

export type RegimeType = "RISK_ON" | "RISK_OFF" | "NEUTRAL" | string;

interface RegimeBadgeProps {
  regime?: RegimeType | null;
  confidence?: number | null;
  showConfidence?: boolean;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function RegimeBadge({
  regime = "NEUTRAL",
  confidence,
  showConfidence = true,
  size = "md",
  className = "",
}: RegimeBadgeProps) {
  const norm = (regime ?? "NEUTRAL").toUpperCase();

  const isRiskOn = norm.includes("RISK_ON") || norm.includes("BULL");
  const isRiskOff = norm.includes("RISK_OFF") || norm.includes("BEAR");

  let label = "NEUTRAL";
  let colorStyles = "bg-[var(--color-info-bg)] text-[var(--color-info)] border-[var(--color-info-border)]";
  let Icon = Minus;

  if (isRiskOn) {
    label = "RISK-ON";
    colorStyles = "bg-[var(--color-positive-bg)] text-[var(--color-positive)] border-[var(--color-positive-border)]";
    Icon = TrendingUp;
  } else if (isRiskOff) {
    label = "RISK-OFF";
    colorStyles = "bg-[var(--color-negative-bg)] text-[var(--color-negative)] border-[var(--color-negative-border)]";
    Icon = isRiskOff && norm.includes("OFF") ? ShieldAlert : TrendingDown;
  }

  const sizeStyles = {
    sm: "text-[10px] px-2 py-0.5 gap-1",
    md: "text-xs px-2.5 py-1 gap-1.5",
    lg: "text-sm px-3.5 py-1.5 gap-2 font-semibold",
  }[size];

  const iconSizes = {
    sm: "w-3 h-3",
    md: "w-3.5 h-3.5",
    lg: "w-4 h-4",
  }[size];

  const confPercent =
    confidence !== null && confidence !== undefined && !Number.isNaN(confidence)
      ? `${Math.round(confidence <= 1 ? confidence * 100 : confidence)}%`
      : null;

  return (
    <div
      role="status"
      aria-label={`Market Regime: ${label}${confPercent ? `, Confidence: ${confPercent}` : ""}`}
      className={`inline-flex items-center rounded-[var(--radius-sm)] border font-mono font-medium tracking-wide ${colorStyles} ${sizeStyles} ${className}`}
      title={`Market Regime: ${label} ${confPercent ? `(${confPercent} confidence)` : ""}`}
    >
      <Icon className={`${iconSizes} shrink-0`} aria-hidden="true" />
      <span className="font-semibold">{label}</span>
      {showConfidence && confPercent && (
        <span className="opacity-80 text-[0.9em] border-l border-current/30 pl-1.5 ml-0.5">
          {confPercent}
        </span>
      )}
    </div>
  );
}
