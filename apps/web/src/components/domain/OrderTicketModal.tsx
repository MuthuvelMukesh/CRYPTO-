"use client";

import React, { useState, useId } from "react";
import {
  X,
  ShieldCheck,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  XCircle,
  Clock,
  Sparkles,
  TrendingUp,
  TrendingDown,
} from "lucide-react";
import { formatPrice, formatPercent, EMPTY_FALLBACK } from "@/lib/format";
import { apiClient } from "@/lib/api/client";

interface OrderTicketModalProps {
  symbol: string;
  currentPrice: number | null | undefined;
  isStale?: boolean;
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export function OrderTicketModal({
  symbol,
  currentPrice,
  isStale = false,
  isOpen,
  onClose,
  onSuccess,
}: OrderTicketModalProps) {
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [orderType, setOrderType] = useState<"MARKET" | "LIMIT">("MARKET");
  const [amountType, setAmountType] = useState<"USD" | "QTY">("USD");
  const [amountValue, setAmountValue] = useState<string>("1000");
  const [limitPrice, setLimitPrice] = useState<string>(
    currentPrice ? String(currentPrice) : ""
  );
  const [stopLossPct, setStopLossPct] = useState<string>("5.0");
  const [takeProfitPct, setTakeProfitPct] = useState<string>("15.0");

  const [step, setStep] = useState<"FORM" | "PREVIEW" | "SUBMITTING" | "SUCCESS">("FORM");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const priceNum =
    orderType === "LIMIT"
      ? Number.parseFloat(limitPrice) || (currentPrice ?? 0)
      : currentPrice ?? 0;

  const numAmount = Number.parseFloat(amountValue) || 0;
  const quantity =
    amountType === "USD" ? (priceNum > 0 ? numAmount / priceNum : 0) : numAmount;
  const notionalUSD =
    amountType === "USD" ? numAmount : quantity * priceNum;

  // Fee and slippage estimates (0.1% fee + 0.05% estimated slippage)
  const feeUSD = notionalUSD * 0.001;
  const slippageUSD = notionalUSD * 0.0005;
  const totalCostUSD = side === "BUY" ? notionalUSD + feeUSD + slippageUSD : notionalUSD - feeUSD - slippageUSD;

  // Bracket stop/tp calculations
  const stopLossPrice =
    side === "BUY"
      ? priceNum * (1 - (Number.parseFloat(stopLossPct) || 0) / 100)
      : priceNum * (1 + (Number.parseFloat(stopLossPct) || 0) / 100);

  const takeProfitPrice =
    side === "BUY"
      ? priceNum * (1 + (Number.parseFloat(takeProfitPct) || 0) / 100)
      : priceNum * (1 - (Number.parseFloat(takeProfitPct) || 0) / 100);

  // Risk Check Validations
  const riskChecks = [
    {
      label: "Fresh Market Data Check",
      passed: !isStale && priceNum > 0,
      reason: isStale ? "Price is stale (>60s old). Live execution disabled." : "Price data is fresh and validated.",
      critical: true,
    },
    {
      label: "Position Sizing Threshold",
      passed: notionalUSD > 0 && notionalUSD <= 15000,
      reason: notionalUSD > 15000 ? "Order exceeds 15% max position risk limit ($15,000)." : "Within configured 15% single-asset limit.",
      critical: true,
    },
    {
      label: "Non-Zero Allocation",
      passed: quantity > 0,
      reason: quantity <= 0 ? "Quantity must be greater than zero." : "Allocation is valid.",
      critical: true,
    },
  ];

  const allChecksPassed = riskChecks.every((c) => c.passed);

  const handleSubmitOrder = async () => {
    setStep("SUBMITTING");
    setErrorMsg(null);

    try {
      const idempotencyKey = `paper-order-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

      const { data, error } = await apiClient.POST("/api/v1/paper/orders", {
        body: {
          account_id: "default_paper",
          symbol: symbol.toUpperCase(),
          side: side,
          order_type: orderType,
          quantity: quantity,
          limit_price: orderType === "LIMIT" ? priceNum : undefined,
          stop_price: stopLossPct ? stopLossPrice : undefined,
          idempotency_key: idempotencyKey,
        },
      });

      if (error) {
        throw new Error((error as any)?.detail || "Failed to submit paper order.");
      }

      setStep("SUCCESS");
      setTimeout(() => {
        onSuccess?.();
        onClose();
      }, 1500);
    } catch (err: any) {
      setErrorMsg(err?.message || "Execution engine rejected order.");
      setStep("PREVIEW");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs">
      <div className="w-full max-w-lg rounded-[var(--radius-md)] border border-[var(--border-strong)] bg-[var(--bg-surface)] shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border-subtle)] bg-[var(--bg-card)]">
          <div className="flex items-center gap-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                side === "BUY" ? "bg-emerald-400" : "bg-rose-400"
              }`}
            />
            <h2 className="text-sm font-bold text-white tracking-wide">
              Paper Order Ticket — {symbol}/USDT
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded text-[var(--text-muted)] hover:text-white transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Invariant 1 Warning Banner */}
        <div className="px-5 py-2 bg-amber-500/10 border-b border-amber-500/20 flex items-center gap-2 text-[11px] font-mono text-amber-300">
          <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
          <span>Paper trading simulation only. No live funds or real exchange keys.</span>
        </div>

        {/* Content Body */}
        <div className="p-5 space-y-4">
          {errorMsg && (
            <div className="p-3 rounded-[var(--radius-sm)] bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {step === "FORM" && (
            <>
              {/* Buy / Sell Selector */}
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setSide("BUY")}
                  className={`py-2 rounded-[var(--radius-sm)] font-mono text-xs font-bold transition flex items-center justify-center gap-1.5 ${
                    side === "BUY"
                      ? "bg-emerald-500 text-white shadow-lg shadow-emerald-500/20"
                      : "bg-[var(--bg-card)] text-[var(--text-muted)] border border-[var(--border-subtle)] hover:text-white"
                  }`}
                >
                  <TrendingUp className="w-3.5 h-3.5" />
                  BUY / LONG
                </button>
                <button
                  type="button"
                  onClick={() => setSide("SELL")}
                  className={`py-2 rounded-[var(--radius-sm)] font-mono text-xs font-bold transition flex items-center justify-center gap-1.5 ${
                    side === "SELL"
                      ? "bg-rose-500 text-white shadow-lg shadow-rose-500/20"
                      : "bg-[var(--bg-card)] text-[var(--text-muted)] border border-[var(--border-subtle)] hover:text-white"
                  }`}
                >
                  <TrendingDown className="w-3.5 h-3.5" />
                  SELL / SHORT
                </button>
              </div>

              {/* Order Type & Current Benchmark Price */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-mono uppercase text-[var(--text-dim)] block mb-1">
                    Order Type
                  </label>
                  <select
                    value={orderType}
                    onChange={(e) => setOrderType(e.target.value as any)}
                    className="w-full px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs font-mono text-white focus:outline-hidden focus:border-sky-500"
                  >
                    <option value="MARKET">Market Execution</option>
                    <option value="LIMIT">Limit Order</option>
                  </select>
                </div>

                <div>
                  <label className="text-[10px] font-mono uppercase text-[var(--text-dim)] block mb-1">
                    Reference Price
                  </label>
                  <div className="px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs font-mono font-bold text-white">
                    {formatPrice(currentPrice)}
                  </div>
                </div>
              </div>

              {/* Limit Price Input if LIMIT */}
              {orderType === "LIMIT" && (
                <div>
                  <label className="text-[10px] font-mono uppercase text-[var(--text-dim)] block mb-1">
                    Limit Price ($)
                  </label>
                  <input
                    type="number"
                    step="any"
                    value={limitPrice}
                    onChange={(e) => setLimitPrice(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs font-mono text-white focus:outline-hidden focus:border-sky-500"
                    placeholder="Enter limit price"
                  />
                </div>
              )}

              {/* Amount Input */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-[10px] font-mono uppercase text-[var(--text-dim)]">
                    Allocation Amount
                  </label>
                  <div className="flex gap-1 text-[10px] font-mono">
                    <button
                      type="button"
                      onClick={() => setAmountType("USD")}
                      className={`px-1.5 py-0.2 rounded ${
                        amountType === "USD" ? "bg-sky-500/20 text-sky-300 font-bold" : "text-[var(--text-dim)]"
                      }`}
                    >
                      USD ($)
                    </button>
                    <span className="text-[var(--text-dim)]">/</span>
                    <button
                      type="button"
                      onClick={() => setAmountType("QTY")}
                      className={`px-1.5 py-0.2 rounded ${
                        amountType === "QTY" ? "bg-sky-500/20 text-sky-300 font-bold" : "text-[var(--text-dim)]"
                      }`}
                    >
                      Units ({symbol})
                    </button>
                  </div>
                </div>

                <div className="relative">
                  <input
                    type="number"
                    step="any"
                    value={amountValue}
                    onChange={(e) => setAmountValue(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs font-mono text-white focus:outline-hidden focus:border-sky-500"
                    placeholder="1000"
                  />
                </div>

                <div className="flex justify-between items-center text-[10px] font-mono text-[var(--text-dim)] mt-1">
                  <span>
                    Est. Qty: <strong className="text-white">{quantity.toFixed(4)}</strong> {symbol}
                  </span>
                  <span>
                    Est. Notional: <strong className="text-white">${notionalUSD.toFixed(2)}</strong>
                  </span>
                </div>
              </div>

              {/* Bracket Stop Loss & Take Profit */}
              <div className="grid grid-cols-2 gap-3 pt-2 border-t border-[var(--border-subtle)]">
                <div>
                  <label className="text-[10px] font-mono uppercase text-[var(--text-dim)] block mb-1">
                    Stop Loss (%)
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    value={stopLossPct}
                    onChange={(e) => setStopLossPct(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs font-mono text-white focus:outline-hidden focus:border-rose-500"
                    placeholder="5.0"
                  />
                  <span className="text-[10px] font-mono text-rose-400 mt-0.5 block">
                    Trigger: {formatPrice(stopLossPrice)}
                  </span>
                </div>

                <div>
                  <label className="text-[10px] font-mono uppercase text-[var(--text-dim)] block mb-1">
                    Take Profit (%)
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    value={takeProfitPct}
                    onChange={(e) => setTakeProfitPct(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs font-mono text-white focus:outline-hidden focus:border-emerald-500"
                    placeholder="15.0"
                  />
                  <span className="text-[10px] font-mono text-emerald-400 mt-0.5 block">
                    Trigger: {formatPrice(takeProfitPrice)}
                  </span>
                </div>
              </div>
            </>
          )}

          {step === "PREVIEW" && (
            <div className="space-y-4">
              {/* Order Summary Box */}
              <div className="rounded-[var(--radius-sm)] bg-[var(--bg-card)] p-3 border border-[var(--border-subtle)] space-y-2 text-xs font-mono">
                <div className="flex justify-between items-center">
                  <span className="text-[var(--text-dim)]">Action:</span>
                  <span className={`font-bold ${side === "BUY" ? "text-emerald-400" : "text-rose-400"}`}>
                    {side} {symbol} ({orderType})
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-[var(--text-dim)]">Execution Price:</span>
                  <span className="text-white font-bold">{formatPrice(priceNum)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-[var(--text-dim)]">Order Quantity:</span>
                  <span className="text-white">{quantity.toFixed(4)} {symbol}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-[var(--text-dim)]">Est. Slippage &amp; Fees:</span>
                  <span className="text-white">${(feeUSD + slippageUSD).toFixed(2)}</span>
                </div>
                <div className="flex justify-between items-center pt-2 border-t border-[var(--border-subtle)]">
                  <span className="text-white font-semibold">Total Settlement:</span>
                  <span className="text-sky-400 font-bold">${totalCostUSD.toFixed(2)}</span>
                </div>
              </div>

              {/* Risk Checks List (Section 7.5 requirement) */}
              <div>
                <span className="text-[10px] uppercase font-mono text-[var(--text-dim)] block mb-1.5">
                  Pre-Trade Risk Engine Checks
                </span>
                <div className="space-y-1.5">
                  {riskChecks.map((chk) => (
                    <div
                      key={chk.label}
                      className={`p-2 rounded-[var(--radius-sm)] border text-xs flex items-start gap-2 ${
                        chk.passed
                          ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                          : "bg-rose-500/10 border-rose-500/20 text-rose-300"
                      }`}
                    >
                      {chk.passed ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                      ) : (
                        <XCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                      )}
                      <div>
                        <strong className="block font-mono text-white text-[11px]">{chk.label}</strong>
                        <span className="text-[10px] opacity-90">{chk.reason}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {step === "SUBMITTING" && (
            <div className="py-8 text-center space-y-3">
              <div className="w-8 h-8 rounded-full border-2 border-sky-400 border-t-transparent animate-spin mx-auto" />
              <p className="text-xs font-mono text-[var(--text-muted)]">
                Routing simulated order to local paper broker ledger...
              </p>
            </div>
          )}

          {step === "SUCCESS" && (
            <div className="py-8 text-center space-y-2">
              <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto" />
              <h3 className="text-sm font-bold text-white">Paper Order Executed</h3>
              <p className="text-xs font-mono text-[var(--text-muted)]">
                Fill appended to immutable audit ledger.
              </p>
            </div>
          )}
        </div>

        {/* Modal Footer Controls */}
        <div className="px-5 py-3 border-t border-[var(--border-subtle)] bg-[var(--bg-card)] flex items-center justify-between">
          {step === "FORM" && (
            <>
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-1.5 rounded-[var(--radius-sm)] text-xs text-[var(--text-muted)] hover:text-white transition font-mono"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => setStep("PREVIEW")}
                disabled={quantity <= 0}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-[var(--radius-sm)] bg-sky-500 text-white font-mono text-xs font-semibold hover:bg-sky-400 transition disabled:opacity-50"
              >
                <span>Preview Order</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </>
          )}

          {step === "PREVIEW" && (
            <>
              <button
                type="button"
                onClick={() => setStep("FORM")}
                className="px-3 py-1.5 rounded-[var(--radius-sm)] text-xs text-[var(--text-muted)] hover:text-white transition font-mono"
              >
                Back to Edit
              </button>
              <button
                type="button"
                onClick={handleSubmitOrder}
                disabled={!allChecksPassed}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-[var(--radius-sm)] bg-emerald-500 text-white font-mono text-xs font-semibold hover:bg-emerald-400 transition disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-emerald-500/20"
              >
                <span>Confirm Paper Trade</span>
              </button>
            </>
          )}

          {(step === "SUBMITTING" || step === "SUCCESS") && <div />}
        </div>
      </div>
    </div>
  );
}
