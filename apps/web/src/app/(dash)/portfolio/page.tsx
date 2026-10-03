"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Briefcase,
  ShieldCheck,
  ShieldAlert,
  RotateCcw,
  RefreshCw,
  Plus,
  ShoppingCart,
  TrendingUp,
  TrendingDown,
  DollarSign,
  AlertTriangle,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
  XCircle,
  CheckCircle2,
} from "lucide-react";

import { apiClient } from "@/lib/api/client";
import { formatPrice, formatPercent, formatRelativeTime, formatUTC, EMPTY_FALLBACK } from "@/lib/format";
import { DeltaCell, EmptyState, ErrorState, CardSkeleton } from "@/components/data";
import { EquityChart, type EquityPoint } from "@/components/charts/EquityChart";
import { OrderTicketModal } from "@/components/domain/OrderTicketModal";
import { AccountResetModal } from "@/components/domain/AccountResetModal";

interface PositionItem {
  symbol: string;
  side: string;
  quantity: number;
  entry_price: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  weight_pct: number;
  stop_loss_price?: number | null;
  take_profit_price?: number | null;
  entry_time?: string;
}

interface PortfolioSummary {
  account_id: string;
  cash_balance: number;
  total_equity: number;
  unrealized_pnl: number;
  realized_pnl: number;
  daily_pnl: number;
  position_count: number;
  gross_exposure: number;
  net_exposure: number;
  current_drawdown_pct: number;
  peak_equity: number;
  circuit_breaker_triggered: boolean;
  open_positions: PositionItem[];
}

interface OrderRecord {
  id: string;
  account_id: string;
  asset_id: string;
  order_type: string;
  side: string;
  quantity: number;
  limit_price?: number | null;
  stop_price?: number | null;
  status: string;
  created_at?: string;
  fills: Array<{
    fill_id: string;
    time?: string;
    fill_price: number;
    quantity: number;
    fee_usd: number;
    slippage_usd: number;
  }>;
}

interface FillRecord {
  id: string;
  order_id: string;
  time?: string;
  fill_price: number;
  quantity: number;
  fee_usd: number;
  slippage_usd: number;
}

interface LedgerRecord {
  id: string;
  event_type: string;
  account_id: string;
  order_id?: string | null;
  asset_id?: string | null;
  quantity?: number | null;
  price?: number | null;
  amount_usd?: number | null;
  cash_balance_after?: number | null;
  data_mode: string;
  created_at: string;
}

interface ReconciliationState {
  account_id: string;
  passed: boolean;
  discrepancy_count: number;
  discrepancies: string[];
  replayed_cash: string;
  actual_cash: string;
  events_replayed: number;
}

export default function PortfolioPage() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [orders, setOrders] = useState<OrderRecord[]>([]);
  const [fills, setFills] = useState<FillRecord[]>([]);
  const [ledger, setLedger] = useState<LedgerRecord[]>([]);
  const [reconciliation, setReconciliation] = useState<ReconciliationState | null>(null);

  const [activeTab, setActiveTab] = useState<"positions" | "orders" | "fills" | "ledger">("positions");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [orderModalOpen, setOrderModalOpen] = useState(false);
  const [resetModalOpen, setResetModalOpen] = useState(false);
  const [closingSymbol, setClosingSymbol] = useState<string | null>(null);

  const fetchPortfolio = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      // 1. Portfolio summary & positions
      const accRes = await apiClient.GET("/api/v1/paper/account", {
        params: { query: { account_id: "default_paper" } },
      });
      if (accRes.data) {
        setSummary(accRes.data as unknown as PortfolioSummary);
      }

      // 2. Reconciliation Audit
      try {
        const reconRes = await apiClient.GET("/api/v1/paper/reconcile", {
          params: { query: { account_id: "default_paper" } },
        });
        if (reconRes.data) {
          setReconciliation(reconRes.data as ReconciliationState);
        }
      } catch {
        // Non-blocking
      }

      // 3. Orders history
      try {
        const ordRes = await apiClient.GET("/api/v1/paper/orders", {
          params: { query: { account_id: "default_paper", limit: 50 } },
        });
        if (ordRes.data && "orders" in ordRes.data) {
          setOrders((ordRes.data as any).orders || []);
        }
      } catch {
        // Non-blocking
      }

      // 4. Execution Fills
      try {
        const fillRes = await apiClient.GET("/api/v1/paper/fills", {
          params: { query: { account_id: "default_paper", limit: 50 } },
        });
        if (fillRes.data && "fills" in fillRes.data) {
          setFills((fillRes.data as any).fills || []);
        }
      } catch {
        // Non-blocking
      }

      // 5. Immutable Ledger Events
      try {
        const ledgRes = await apiClient.GET("/api/v1/paper/ledger", {
          params: { query: { account_id: "default_paper", limit: 50 } },
        });
        if (ledgRes.data && "events" in ledgRes.data) {
          setLedger((ledgRes.data as any).events || []);
        }
      } catch {
        // Non-blocking
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load paper brokerage portfolio data.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchPortfolio();
  }, [fetchPortfolio]);

  const handleClosePosition = async (sym: string) => {
    setClosingSymbol(sym);
    try {
      const { data, error } = await apiClient.POST(
        "/api/v1/paper/positions/{symbol}/close" as any,
        {
          params: {
            path: { symbol: sym },
            query: { account_id: "default_paper" },
          },
        }
      );
      if (error) {
        throw new Error((error as any)?.detail || `Failed to liquidate ${sym}`);
      }
      await fetchPortfolio(true);
    } catch (err: any) {
      alert(err?.message || "Error liquidating position");
    } finally {
      setClosingSymbol(null);
    }
  };

  const currentEquity = summary?.total_equity ?? null;
  const cashBalance = summary?.cash_balance ?? null;
  const unrealizedPnl = summary?.unrealized_pnl ?? null;
  const dailyPnl = summary?.daily_pnl ?? null;
  const drawdown = summary?.current_drawdown_pct ?? null;

  // Build equity points if summary is loaded with real numbers
  const equityPoints: EquityPoint[] =
    currentEquity !== null && cashBalance !== null
      ? [
          {
            time: new Date(Date.now() - 3600000 * 24).toISOString(),
            equity: currentEquity,
            cash: cashBalance,
          },
          {
            time: new Date().toISOString(),
            equity: currentEquity,
            cash: cashBalance,
            drawdown_pct: drawdown ?? 0,
          },
        ]
      : [];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[var(--border-subtle)] gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              Paper Portfolio &amp; Brokerage
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold">
              PAPER TRADING ONLY
            </span>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Mark-to-market positions, risk telemetry, open orders, and immutable audit ledger.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Reconciliation Badge */}
          {reconciliation && (
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono font-medium border ${
                reconciliation.passed
                  ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                  : "bg-rose-500/10 border-rose-500/30 text-rose-300"
              }`}
              title={`Reconciled ${reconciliation.events_replayed} ledger events (${reconciliation.discrepancy_count} discrepancies)`}
            >
              {reconciliation.passed ? (
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
              )}
              <span>
                {reconciliation.passed ? "Ledger Reconciled" : "Discrepancy Flag"}
              </span>
            </div>
          )}

          {/* Action Buttons */}
          <button
            type="button"
            onClick={() => setOrderModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] bg-emerald-500 text-white text-xs font-mono font-semibold hover:bg-emerald-400 transition shadow-lg shadow-emerald-500/20"
          >
            <ShoppingCart className="w-3.5 h-3.5" />
            <span>Order Ticket</span>
          </button>

          <button
            type="button"
            onClick={() => setResetModalOpen(true)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-card)] text-xs font-mono text-[var(--text-dim)] hover:text-rose-400 hover:border-rose-500/30 transition"
            title="Reset simulated balance"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset</span>
          </button>

          <button
            type="button"
            onClick={() => fetchPortfolio(true)}
            disabled={refreshing || loading}
            className="p-1.5 rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-card)] text-[var(--text-muted)] hover:text-white transition disabled:opacity-50"
            title="Refresh portfolio"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Circuit Breaker Alert Banner if triggered */}
      {summary?.circuit_breaker_triggered && (
        <div className="p-3 rounded-[var(--radius-sm)] bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>
              <strong>Circuit Breaker Triggered:</strong> Portfolio drawdown exceeded maximum risk limit (15.0%). New paper order submissions are halted.
            </span>
          </div>
          <button
            type="button"
            onClick={() => setResetModalOpen(true)}
            className="text-[11px] font-mono underline font-bold hover:text-white"
          >
            Reset Account
          </button>
        </div>
      )}

      {error && (
        <ErrorState
          title="Portfolio Telemetry Unavailable"
          message={error}
          onRetry={() => fetchPortfolio(false)}
        />
      )}

      {loading && !error ? (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : (
        <>
          {/* Top Performance Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {/* Total Equity */}
            <div className="rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3.5">
              <span className="text-[10px] uppercase font-mono text-[var(--text-dim)] block mb-1">
                Total Equity
              </span>
              <div className="text-xl font-extrabold font-mono text-white">
                {formatPrice(currentEquity)}
              </div>
              <span className="text-[10px] font-mono text-[var(--text-muted)] mt-0.5 block">
                Cash: {formatPrice(cashBalance)}
              </span>
            </div>

            {/* Unrealized PnL */}
            <div className="rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3.5">
              <span className="text-[10px] uppercase font-mono text-[var(--text-dim)] block mb-1">
                Unrealized P&amp;L
              </span>
              <div
                className={`text-xl font-extrabold font-mono ${
                  unrealizedPnl !== null
                    ? unrealizedPnl >= 0
                      ? "text-emerald-400"
                      : "text-rose-400"
                    : "text-white"
                }`}
              >
                {unrealizedPnl !== null && unrealizedPnl > 0 ? "+" : ""}
                {formatPrice(unrealizedPnl)}
              </div>
              <span className="text-[10px] font-mono text-[var(--text-muted)] mt-0.5 block">
                Open Positions: {summary?.position_count ?? 0}
              </span>
            </div>

            {/* Daily Return */}
            <div className="rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3.5">
              <span className="text-[10px] uppercase font-mono text-[var(--text-dim)] block mb-1">
                Day P&amp;L
              </span>
              <div
                className={`text-xl font-extrabold font-mono ${
                  dailyPnl !== null
                    ? dailyPnl >= 0
                      ? "text-emerald-400"
                      : "text-rose-400"
                    : "text-white"
                }`}
              >
                {dailyPnl !== null && dailyPnl > 0 ? "+" : ""}
                {formatPrice(dailyPnl)}
              </div>
              <span className="text-[10px] font-mono text-[var(--text-muted)] mt-0.5 block">
                24h Rolling Performance
              </span>
            </div>

            {/* Gross Exposure */}
            <div className="rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3.5">
              <span className="text-[10px] uppercase font-mono text-[var(--text-dim)] block mb-1">
                Gross Exposure
              </span>
              <div className="text-xl font-extrabold font-mono text-white">
                {formatPrice(summary?.gross_exposure)}
              </div>
              <span className="text-[10px] font-mono text-sky-400 mt-0.5 block">
                {currentEquity && currentEquity > 0 && summary?.gross_exposure !== undefined
                  ? `${(((summary.gross_exposure) / currentEquity) * 100).toFixed(1)}% Allocated`
                  : "—"}
              </span>
            </div>

            {/* Drawdown vs Circuit Breaker */}
            <div className="rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3.5 col-span-2 lg:col-span-1">
              <div className="flex justify-between items-center mb-1">
                <span className="text-[10px] uppercase font-mono text-[var(--text-dim)]">
                  Drawdown
                </span>
                <span className="text-[10px] font-mono text-[var(--text-dim)]">
                  Limit: 15%
                </span>
              </div>
              <div
                className={`text-xl font-extrabold font-mono ${
                  drawdown !== null && drawdown > 10 ? "text-rose-400" : "text-white"
                }`}
              >
                {drawdown !== null ? `-${Math.abs(drawdown).toFixed(2)}%` : EMPTY_FALLBACK}
              </div>
              {/* Progress bar towards circuit breaker */}
              <div className="w-full h-1.5 bg-[var(--bg-card)] rounded-full overflow-hidden mt-1.5 border border-[var(--border-subtle)]">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${
                    drawdown !== null && drawdown > 10 ? "bg-rose-500" : "bg-sky-400"
                  }`}
                  style={{ width: `${drawdown !== null ? Math.min(100, (Math.abs(drawdown) / 15) * 100) : 0}%` }}
                />
              </div>
            </div>
          </div>

          {/* Equity Chart View */}
          <EquityChart
            data={equityPoints}
            peakEquity={summary?.peak_equity}
            startingCapital={100000}
            currentDrawdown={summary?.current_drawdown_pct}
          />

          {/* Tab Navigation System */}
          <div className="border-b border-[var(--border-subtle)] flex items-center justify-between gap-4">
            <div className="flex gap-2">
              {[
                { id: "positions", label: "Open Positions", count: summary?.open_positions?.length ?? 0 },
                { id: "orders", label: "Order History", count: orders.length },
                { id: "fills", label: "Execution Fills", count: fills.length },
                { id: "ledger", label: "Audit Ledger", count: ledger.length },
              ].map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`py-2 px-3 text-xs font-mono font-semibold border-b-2 transition flex items-center gap-1.5 ${
                    activeTab === tab.id
                      ? "border-sky-400 text-sky-400"
                      : "border-transparent text-[var(--text-muted)] hover:text-white"
                  }`}
                >
                  <span>{tab.label}</span>
                  <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-[var(--bg-card)] text-[var(--text-dim)]">
                    {tab.count}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Tab Content Display */}
          <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] overflow-hidden">
            {/* Tab 1: Open Positions */}
            {activeTab === "positions" && (
              <div>
                {!summary?.open_positions || summary.open_positions.length === 0 ? (
                  <div className="p-8 text-center">
                    <EmptyState
                      title="No Open Paper Positions"
                      description="Use the Order Ticket to submit simulated trades from the Market Scanner or Asset Station."
                      actionLabel="Open Order Ticket"
                      onAction={() => setOrderModalOpen(true)}
                    />
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs font-mono">
                      <thead className="bg-[var(--bg-card)] text-[10px] uppercase text-[var(--text-dim)] border-b border-[var(--border-subtle)]">
                        <tr>
                          <th className="py-2.5 px-4 font-semibold">Asset Symbol</th>
                          <th className="py-2.5 px-3 font-semibold">Side</th>
                          <th className="py-2.5 px-3 font-semibold text-right">Quantity</th>
                          <th className="py-2.5 px-3 font-semibold text-right">Entry Price</th>
                          <th className="py-2.5 px-3 font-semibold text-right">Mark Price</th>
                          <th className="py-2.5 px-3 font-semibold text-right">Market Value</th>
                          <th className="py-2.5 px-3 font-semibold text-right">Unrealized P&amp;L</th>
                          <th className="py-2.5 px-3 font-semibold text-right">Weight</th>
                          <th className="py-2.5 px-4 font-semibold text-center">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border-subtle)]">
                        {summary.open_positions.map((pos) => (
                          <tr key={pos.symbol} className="hover:bg-[var(--bg-card)]/40 transition">
                            <td className="py-3 px-4 font-bold text-white">
                              <Link
                                href={`/assets/${pos.symbol}`}
                                className="hover:text-sky-400 transition flex items-center gap-1.5"
                              >
                                {pos.symbol}
                              </Link>
                            </td>
                            <td className="py-3 px-3">
                              <span
                                className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                  pos.side === "BUY" || pos.side === "LONG"
                                    ? "bg-emerald-500/20 text-emerald-300"
                                    : "bg-rose-500/20 text-rose-300"
                                }`}
                              >
                                {pos.side}
                              </span>
                            </td>
                            <td className="py-3 px-3 text-right text-white">
                              {pos.quantity.toLocaleString(undefined, { maximumFractionDigits: 4 })}
                            </td>
                            <td className="py-3 px-3 text-right text-[var(--text-secondary)]">
                              {formatPrice(pos.entry_price)}
                            </td>
                            <td className="py-3 px-3 text-right font-semibold text-white">
                              {formatPrice(pos.current_price)}
                            </td>
                            <td className="py-3 px-3 text-right font-semibold text-white">
                              {formatPrice(pos.market_value)}
                            </td>
                            <td className="py-3 px-3 text-right">
                              <div
                                className={`font-bold ${
                                  pos.unrealized_pnl >= 0 ? "text-emerald-400" : "text-rose-400"
                                }`}
                              >
                                {pos.unrealized_pnl >= 0 ? "+" : ""}
                                {formatPrice(pos.unrealized_pnl)}
                              </div>
                              <DeltaCell value={pos.unrealized_pnl_pct} className="text-[10px]" />
                            </td>
                            <td className="py-3 px-3 text-right text-sky-400 font-semibold">
                              {pos.weight_pct.toFixed(1)}%
                            </td>
                            <td className="py-3 px-4 text-center">
                              <button
                                type="button"
                                onClick={() => handleClosePosition(pos.symbol)}
                                disabled={closingSymbol === pos.symbol}
                                className="px-2 py-1 rounded-[var(--radius-sm)] border border-rose-500/30 text-rose-400 hover:bg-rose-500/20 text-[10px] font-bold transition disabled:opacity-50"
                              >
                                {closingSymbol === pos.symbol ? "Closing..." : "Close"}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* Tab 2: Orders History */}
            {activeTab === "orders" && (
              <div>
                {orders.length === 0 ? (
                  <div className="p-8 text-center text-xs text-[var(--text-dim)] font-mono">
                    No order history recorded yet.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs font-mono">
                      <thead className="bg-[var(--bg-card)] text-[10px] uppercase text-[var(--text-dim)] border-b border-[var(--border-subtle)]">
                        <tr>
                          <th className="py-2.5 px-4 font-semibold">Order ID</th>
                          <th className="py-2.5 px-3 font-semibold">Created</th>
                          <th className="py-2.5 px-3 font-semibold">Asset</th>
                          <th className="py-2.5 px-3 font-semibold">Side</th>
                          <th className="py-2.5 px-3 font-semibold">Type</th>
                          <th className="py-2.5 px-3 font-semibold text-right">Quantity</th>
                          <th className="py-2.5 px-3 font-semibold text-right">Price</th>
                          <th className="py-2.5 px-4 font-semibold text-right">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border-subtle)]">
                        {orders.map((ord) => (
                          <tr key={ord.id} className="hover:bg-[var(--bg-card)]/40 transition">
                            <td className="py-2.5 px-4 text-[var(--text-dim)] truncate max-w-[100px]">
                              {ord.id.slice(0, 8)}...
                            </td>
                            <td className="py-2.5 px-3 text-[var(--text-secondary)]">
                              {formatRelativeTime(ord.created_at)}
                            </td>
                            <td className="py-2.5 px-3 font-bold text-white">
                              {ord.asset_id}
                            </td>
                            <td className="py-2.5 px-3">
                              <span
                                className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                                  ord.side === "BUY" ? "text-emerald-400" : "text-rose-400"
                                }`}
                              >
                                {ord.side}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 text-[var(--text-dim)]">{ord.order_type}</td>
                            <td className="py-2.5 px-3 text-right text-white">
                              {ord.quantity.toFixed(4)}
                            </td>
                            <td className="py-2.5 px-3 text-right text-white">
                              {ord.limit_price ? formatPrice(ord.limit_price) : "MARKET"}
                            </td>
                            <td className="py-2.5 px-4 text-right">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  ord.status === "FILLED"
                                    ? "bg-emerald-500/20 text-emerald-300"
                                    : ord.status === "CANCELLED"
                                    ? "bg-rose-500/20 text-rose-300"
                                    : "bg-sky-500/20 text-sky-300"
                                }`}
                              >
                                {ord.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* Tab 3: Execution Fills */}
            {activeTab === "fills" && (
              <div>
                {fills.length === 0 ? (
                  <div className="p-8 text-center text-xs text-[var(--text-dim)] font-mono">
                    No execution fills recorded yet.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs font-mono">
                      <thead className="bg-[var(--bg-card)] text-[10px] uppercase text-[var(--text-dim)] border-b border-[var(--border-subtle)]">
                        <tr>
                          <th className="py-2.5 px-4 font-semibold">Fill ID</th>
                          <th className="py-2.5 px-3 font-semibold">Time</th>
                          <th className="py-2.5 px-3 font-semibold text-right">Fill Price</th>
                          <th className="py-2.5 px-3 font-semibold text-right">Quantity</th>
                          <th className="py-2.5 px-3 font-semibold text-right">Fee ($)</th>
                          <th className="py-2.5 px-4 font-semibold text-right">Slippage ($)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border-subtle)]">
                        {fills.map((fill) => (
                          <tr key={fill.id} className="hover:bg-[var(--bg-card)]/40 transition">
                            <td className="py-2.5 px-4 text-[var(--text-dim)] truncate max-w-[120px]">
                              {fill.id.slice(0, 10)}...
                            </td>
                            <td className="py-2.5 px-3 text-[var(--text-secondary)]">
                              {formatRelativeTime(fill.time)}
                            </td>
                            <td className="py-2.5 px-3 text-right font-bold text-white">
                              {formatPrice(fill.fill_price)}
                            </td>
                            <td className="py-2.5 px-3 text-right text-white">
                              {fill.quantity.toFixed(4)}
                            </td>
                            <td className="py-2.5 px-3 text-right text-[var(--text-dim)]">
                              ${fill.fee_usd.toFixed(2)}
                            </td>
                            <td className="py-2.5 px-4 text-right text-[var(--text-dim)]">
                              ${fill.slippage_usd.toFixed(2)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* Tab 4: Immutable Audit Ledger */}
            {activeTab === "ledger" && (
              <div>
                {ledger.length === 0 ? (
                  <div className="p-8 text-center text-xs text-[var(--text-dim)] font-mono">
                    Audit ledger is empty.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs font-mono">
                      <thead className="bg-[var(--bg-card)] text-[10px] uppercase text-[var(--text-dim)] border-b border-[var(--border-subtle)]">
                        <tr>
                          <th className="py-2.5 px-4 font-semibold">Event ID</th>
                          <th className="py-2.5 px-3 font-semibold">Event Type</th>
                          <th className="py-2.5 px-3 font-semibold">Asset</th>
                          <th className="py-2.5 px-3 font-semibold text-right">Quantity</th>
                          <th className="py-2.5 px-3 font-semibold text-right">Price</th>
                          <th className="py-2.5 px-3 font-semibold text-right">Amount ($)</th>
                          <th className="py-2.5 px-3 font-semibold text-right">Cash Balance After</th>
                          <th className="py-2.5 px-4 font-semibold text-right">Timestamp</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border-subtle)]">
                        {ledger.map((evt) => (
                          <tr key={evt.id} className="hover:bg-[var(--bg-card)]/40 transition">
                            <td className="py-2.5 px-4 text-[var(--text-dim)] truncate max-w-[100px]">
                              {evt.id.slice(0, 8)}...
                            </td>
                            <td className="py-2.5 px-3">
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-[var(--bg-card)] border border-[var(--border-subtle)] text-sky-300">
                                {evt.event_type}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 font-bold text-white">
                              {evt.asset_id || "USD"}
                            </td>
                            <td className="py-2.5 px-3 text-right text-white">
                              {evt.quantity !== null && evt.quantity !== undefined
                                ? evt.quantity.toFixed(4)
                                : "—"}
                            </td>
                            <td className="py-2.5 px-3 text-right text-white">
                              {evt.price !== null && evt.price !== undefined
                                ? formatPrice(evt.price)
                                : "—"}
                            </td>
                            <td className="py-2.5 px-3 text-right font-bold text-white">
                              {evt.amount_usd !== null && evt.amount_usd !== undefined
                                ? formatPrice(evt.amount_usd)
                                : "—"}
                            </td>
                            <td className="py-2.5 px-3 text-right font-mono font-bold text-emerald-400">
                              {evt.cash_balance_after !== null && evt.cash_balance_after !== undefined
                                ? formatPrice(evt.cash_balance_after)
                                : "—"}
                            </td>
                            <td className="py-2.5 px-4 text-right text-[var(--text-dim)]" title={formatUTC(evt.created_at)}>
                              {formatRelativeTime(evt.created_at)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}

      {/* Order Ticket Modal */}
      <OrderTicketModal
        symbol="BTC"
        currentPrice={null}
        isOpen={orderModalOpen}
        onClose={() => setOrderModalOpen(false)}
        onSuccess={() => fetchPortfolio(true)}
      />

      {/* Account Reset Modal */}
      <AccountResetModal
        isOpen={resetModalOpen}
        onClose={() => setResetModalOpen(false)}
        onSuccess={() => fetchPortfolio(true)}
      />
    </div>
  );
}
