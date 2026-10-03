"use client";

import React, { useState } from "react";
import { X, AlertTriangle, RotateCcw, CheckCircle2 } from "lucide-react";
import { apiClient } from "@/lib/api/client";

interface AccountResetModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  currentAccountId?: string;
}

export function AccountResetModal({
  isOpen,
  onClose,
  onSuccess,
  currentAccountId = "default_paper",
}: AccountResetModalProps) {
  const [typedConfirmation, setTypedConfirmation] = useState("");
  const [startingBalance, setStartingBalance] = useState("100000");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const isConfirmed = typedConfirmation.trim() === "RESET";

  const handleReset = async () => {
    if (!isConfirmed) return;
    setLoading(true);
    setErrorMsg(null);

    try {
      const balanceNum = Number.parseFloat(startingBalance) || 100000;
      const { data, error } = await apiClient.POST("/api/v1/paper/reset", {
        body: {
          account_id: currentAccountId,
          starting_balance: balanceNum,
        },
      });

      if (error) {
        throw new Error((error as any)?.detail || "Failed to reset paper account.");
      }

      onSuccess?.();
      onClose();
    } catch (err: any) {
      setErrorMsg(err?.message || "Virtual broker rejected reset request.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-xs">
      <div className="w-full max-w-md rounded-[var(--radius-md)] border border-rose-500/40 bg-[var(--bg-surface)] shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border-subtle)] bg-[var(--bg-card)]">
          <div className="flex items-center gap-2 text-rose-400">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <h2 className="text-sm font-bold text-white tracking-wide">
              Reset Virtual Paper Account
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

        {/* Content Body */}
        <div className="p-5 space-y-4 text-xs font-mono">
          <div className="p-3 rounded-[var(--radius-sm)] bg-rose-500/10 border border-rose-500/20 text-rose-300 space-y-1">
            <strong className="block text-white font-semibold">Irreversible Action:</strong>
            <p className="text-[11px] opacity-90">
              Resetting will close all active positions at current market prices and wipe simulated
              order queue. All historical ledger events will remain archived in the database.
            </p>
          </div>

          {errorMsg && (
            <div className="p-2.5 rounded bg-rose-500/20 border border-rose-500/30 text-rose-200">
              {errorMsg}
            </div>
          )}

          <div>
            <label className="text-[10px] uppercase text-[var(--text-dim)] block mb-1">
              Starting Cash Capital ($)
            </label>
            <input
              type="number"
              step="1000"
              value={startingBalance}
              onChange={(e) => setStartingBalance(e.target.value)}
              className="w-full px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs text-white focus:outline-hidden focus:border-sky-500"
            />
          </div>

          <div>
            <label className="text-[10px] uppercase text-[var(--text-dim)] block mb-1">
              Type <strong className="text-white">RESET</strong> to confirm
            </label>
            <input
              type="text"
              value={typedConfirmation}
              onChange={(e) => setTypedConfirmation(e.target.value)}
              placeholder="RESET"
              className="w-full px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs text-white uppercase focus:outline-hidden focus:border-rose-500"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-[var(--border-subtle)] bg-[var(--bg-card)] flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 rounded text-xs text-[var(--text-muted)] hover:text-white transition font-mono"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={handleReset}
            disabled={!isConfirmed || loading}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-[var(--radius-sm)] bg-rose-600 text-white font-mono text-xs font-semibold hover:bg-rose-500 transition disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-rose-600/20"
          >
            <RotateCcw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Confirm Account Reset</span>
          </button>
        </div>
      </div>
    </div>
  );
}
