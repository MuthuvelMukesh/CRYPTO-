/**
 * Financial & quant data formatting utilities.
 *
 * CRITICAL RULE (Invariant 2):
 * Never return fabricated numbers or defaults when data is missing.
 * Missing / null / undefined / NaN values MUST format strictly to em-dash ("—").
 */

export const EMPTY_FALLBACK = "—";

/**
 * Format currency with adaptive precision based on magnitude.
 * High-value assets (BTC, ETH) use 2 decimal places.
 * Sub-dollar altcoins and meme tokens retain up to 8 decimal places.
 */
export function formatPrice(
  value: number | string | null | undefined,
  options: { currency?: string; maxDecimals?: number } = {}
): string {
  if (value === null || value === undefined || value === "") {
    return EMPTY_FALLBACK;
  }

  const num = typeof value === "string" ? Number.parseFloat(value) : value;
  if (!Number.isFinite(num)) {
    return EMPTY_FALLBACK;
  }

  const currencyPrefix = options.currency ?? "$";
  const abs = Math.abs(num);

  let decimals = 2;
  if (abs === 0) {
    decimals = 2;
  } else if (abs < 0.01) {
    decimals = 8;
  } else if (abs < 1) {
    decimals = 4;
  } else {
    decimals = 2;
  }

  if (options.maxDecimals !== undefined) {
    decimals = Math.min(decimals, options.maxDecimals);
  }

  const formatted = num.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  return `${currencyPrefix}${formatted}`;
}

/**
 * Format signed percentage changes (+2.50%, -1.20%, 0.00%).
 */
export function formatPercent(
  value: number | string | null | undefined,
  options: { isFraction?: boolean; decimals?: number } = {}
): string {
  if (value === null || value === undefined || value === "") {
    return EMPTY_FALLBACK;
  }

  let num = typeof value === "string" ? Number.parseFloat(value) : value;
  if (!Number.isFinite(num)) {
    return EMPTY_FALLBACK;
  }

  // If provided as decimal ratio (e.g., 0.052 instead of 5.2), convert to percentage
  if (options.isFraction) {
    num *= 100;
  }

  const decimals = options.decimals ?? 2;
  const sign = num > 0 ? "+" : "";
  return `${sign}${num.toFixed(decimals)}%`;
}

/**
 * Format large USD figures into compact financial representations ($1.25B, $45.2M, $850K).
 */
export function formatCompactUSD(
  value: number | string | null | undefined,
  prefix = "$"
): string {
  if (value === null || value === undefined || value === "") {
    return EMPTY_FALLBACK;
  }

  const num = typeof value === "string" ? Number.parseFloat(value) : value;
  if (!Number.isFinite(num)) {
    return EMPTY_FALLBACK;
  }

  const abs = Math.abs(num);
  const sign = num < 0 ? "-" : "";

  if (abs >= 1e12) {
    return `${sign}${prefix}${(abs / 1e12).toFixed(2)}T`;
  }
  if (abs >= 1e9) {
    return `${sign}${prefix}${(abs / 1e9).toFixed(2)}B`;
  }
  if (abs >= 1e6) {
    return `${sign}${prefix}${(abs / 1e6).toFixed(2)}M`;
  }
  if (abs >= 1e3) {
    return `${sign}${prefix}${(abs / 1e3).toFixed(1)}K`;
  }
  return `${sign}${prefix}${abs.toFixed(2)}`;
}

/**
 * Format score (0 to 100) with 1 decimal place.
 */
export function formatScore(
  value: number | string | null | undefined
): string {
  if (value === null || value === undefined || value === "") {
    return EMPTY_FALLBACK;
  }

  const num = typeof value === "string" ? Number.parseFloat(value) : value;
  if (!Number.isFinite(num)) {
    return EMPTY_FALLBACK;
  }

  return num.toFixed(1);
}

/**
 * Format ISO datetime string or Date into compact relative time ("2m ago", "1h ago").
 */
export function formatRelativeTime(
  timestamp: string | Date | null | undefined
): string {
  if (!timestamp) return EMPTY_FALLBACK;

  const date = typeof timestamp === "string" ? new Date(timestamp) : timestamp;
  if (Number.isNaN(date.getTime())) return EMPTY_FALLBACK;

  const now = Date.now();
  const diffSec = Math.floor((now - date.getTime()) / 1000);

  if (diffSec <= 2) return "just now";
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`;

  return date.toISOString().split("T")[0] ?? EMPTY_FALLBACK;
}

/**
 * Format full UTC timestamp for tooltips and audit trails.
 */
export function formatUTC(
  timestamp: string | Date | null | undefined
): string {
  if (!timestamp) return EMPTY_FALLBACK;
  const date = typeof timestamp === "string" ? new Date(timestamp) : timestamp;
  if (Number.isNaN(date.getTime())) return EMPTY_FALLBACK;
  return date.toUTCString();
}
