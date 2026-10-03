"use client";

import React, { useState, useEffect } from "react";
import {
  Bell,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Plus,
  Play,
  Send,
  Trash2,
  Filter,
  RefreshCw,
  Clock,
  ShieldAlert,
  Smartphone,
  MessageSquare,
  Mail,
  Zap,
} from "lucide-react";
import { formatRelativeTime, formatUTC, EMPTY_FALLBACK } from "@/lib/format";

interface AlertItem {
  id: string;
  time: string;
  alert_type: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  asset_id: string;
  message: string;
  details?: Record<string, any>;
  is_read?: boolean;
}

interface AlertRule {
  id: string;
  name: string;
  condition: string;
  threshold: string;
  channels: string[];
  cooldown_minutes: number;
  is_active: boolean;
}

export default function AlertsPage() {
  const [activeTab, setActiveTab] = useState<"INBOX" | "RULES" | "CHANNELS">("INBOX");
  const [loading, setLoading] = useState(true);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");
  const [simulating, setSimulating] = useState(false);
  const [simulateSuccess, setSimulateSuccess] = useState<string | null>(null);

  // Default configured rules
  const [rules, setRules] = useState<AlertRule[]>([
    {
      id: "rule-1",
      name: "Top Alpha Breakout (> 80 Score)",
      condition: "OPPORTUNITY_SCORE_ABOVE",
      threshold: "Score >= 80.0",
      channels: ["IN_APP", "TELEGRAM"],
      cooldown_minutes: 60,
      is_active: true,
    },
    {
      id: "rule-2",
      name: "Market Regime Switch to RISK-OFF",
      condition: "REGIME_CHANGE",
      threshold: "Regime == RISK_OFF",
      channels: ["IN_APP", "DISCORD", "EMAIL"],
      cooldown_minutes: 240,
      is_active: true,
    },
    {
      id: "rule-3",
      name: "Data Ingestion Stale Feed (> 120s)",
      condition: "FEED_STALE",
      threshold: "Lag > 120 seconds",
      channels: ["IN_APP", "DISCORD"],
      cooldown_minutes: 30,
      is_active: true,
    },
    {
      id: "rule-4",
      name: "High Supply Concentration Flag",
      condition: "RISK_FLAG_TRIGGERED",
      threshold: "Flag == SUPPLY_RISK",
      channels: ["IN_APP"],
      cooldown_minutes: 120,
      is_active: false,
    },
  ]);

  // Rule Builder Form State
  const [newRuleName, setNewRuleName] = useState("");
  const [newCondition, setNewCondition] = useState("OPPORTUNITY_SCORE_ABOVE");
  const [newThresholdVal, setNewThresholdVal] = useState("75");
  const [newChannelTelegram, setNewChannelTelegram] = useState(true);
  const [newChannelDiscord, setNewChannelDiscord] = useState(false);
  const [newChannelEmail, setNewChannelEmail] = useState(false);
  const [newCooldown, setNewCooldown] = useState(60);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const url =
        severityFilter !== "ALL"
          ? `/api/proxy/api/v1/alerts?severity=${severityFilter}`
          : "/api/proxy/api/v1/alerts";
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setAlerts(data);
      }
    } catch {
      // Handled via state
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [severityFilter]);

  const handleSimulateAlert = async (type: string, severity: "INFO" | "WARNING" | "CRITICAL") => {
    setSimulating(true);
    setSimulateSuccess(null);
    try {
      const res = await fetch("/api/proxy/api/v1/alerts/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          alert_type: type,
          severity,
          symbol: "SOL",
          message: `Test alert simulated: ${type} with severity ${severity}. Dispatched via SSE broadcaster.`,
          details: { simulated: true, timestamp: new Date().toISOString() },
        }),
      });

      if (res.ok) {
        const newAlert = await res.json();
        setAlerts((prev) => [newAlert, ...prev]);
        setSimulateSuccess(`Dispatched ${severity} alert successfully!`);
        setTimeout(() => setSimulateSuccess(null), 3000);
      }
    } catch {
      // Handled
    } finally {
      setSimulating(false);
    }
  };

  const handleAddRule = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRuleName.trim()) return;

    const channels: string[] = ["IN_APP"];
    if (newChannelTelegram) channels.push("TELEGRAM");
    if (newChannelDiscord) channels.push("DISCORD");
    if (newChannelEmail) channels.push("EMAIL");

    const created: AlertRule = {
      id: `rule-${Date.now()}`,
      name: newRuleName,
      condition: newCondition,
      threshold: `${newCondition}: ${newThresholdVal}`,
      channels,
      cooldown_minutes: newCooldown,
      is_active: true,
    };

    setRules([created, ...rules]);
    setNewRuleName("");
  };

  const toggleRule = (id: string) => {
    setRules(rules.map((r) => (r.id === id ? { ...r, is_active: !r.is_active } : r)));
  };

  const deleteRule = (id: string) => {
    setRules(rules.filter((r) => r.id !== id));
  };

  const getSeverityBadge = (sev: string) => {
    switch (sev.toUpperCase()) {
      case "CRITICAL":
        return "bg-rose-500/20 text-rose-300 border-rose-500/30";
      case "WARNING":
        return "bg-amber-500/20 text-amber-300 border-amber-500/30";
      default:
        return "bg-sky-500/20 text-sky-300 border-sky-500/30";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-[var(--border-subtle)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              Alerts Center & Signal Dispatcher
            </h1>
            <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 font-mono font-medium">
              Dispatcher
            </span>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Real-time event stream triggers, threshold rule builder, Telegram/Discord webhooks, and audit logs.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* Navigation Tabs */}
          <div className="flex items-center bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-[var(--radius-sm)] p-0.5 text-xs font-mono">
            {(["INBOX", "RULES", "CHANNELS"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-3 py-1 rounded-[var(--radius-sm)] transition ${
                  activeTab === tab
                    ? "bg-[var(--bg-card)] text-white font-bold shadow-sm"
                    : "text-[var(--text-dim)] hover:text-white"
                }`}
              >
                {tab === "INBOX" ? `INBOX (${alerts.length})` : tab}
              </button>
            ))}
          </div>

          <button
            onClick={fetchAlerts}
            disabled={loading}
            className="p-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-dim)] hover:text-white transition disabled:opacity-50"
            title="Refresh alerts"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Simulation Feedback Alert */}
      {simulateSuccess && (
        <div className="rounded-[var(--radius-sm)] border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs font-mono text-emerald-300 flex items-center gap-2 animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{simulateSuccess}</span>
        </div>
      )}

      {/* Tab 1: Alert Inbox */}
      {activeTab === "INBOX" && (
        <div className="space-y-4">
          {/* Filter Bar & Quick Test Emission */}
          <div className="p-3.5 rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
            <div className="flex items-center gap-2">
              <span className="text-[var(--text-dim)]">Severity:</span>
              <div className="flex items-center bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-[var(--radius-sm)] p-0.5">
                {(["ALL", "INFO", "WARNING", "CRITICAL"] as const).map((sev) => (
                  <button
                    key={sev}
                    onClick={() => setSeverityFilter(sev)}
                    className={`px-2 py-0.5 rounded-[var(--radius-sm)] transition ${
                      severityFilter === sev
                        ? "bg-white/10 text-white font-bold"
                        : "text-[var(--text-dim)] hover:text-white"
                    }`}
                  >
                    {sev}
                  </button>
                ))}
              </div>
            </div>

            {/* Test Simulation Controls */}
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-[var(--text-dim)]">Simulate Trigger:</span>
              <button
                onClick={() => handleSimulateAlert("MOMENTUM_BREAKOUT", "INFO")}
                disabled={simulating}
                className="px-2.5 py-1 rounded bg-sky-600/20 border border-sky-500/30 text-sky-300 text-[11px] font-medium hover:bg-sky-600/30 transition disabled:opacity-50"
              >
                + Breakout (Info)
              </button>
              <button
                onClick={() => handleSimulateAlert("RISK_PENALTY", "WARNING")}
                disabled={simulating}
                className="px-2.5 py-1 rounded bg-amber-600/20 border border-amber-500/30 text-amber-300 text-[11px] font-medium hover:bg-amber-600/30 transition disabled:opacity-50"
              >
                + Risk Warning
              </button>
              <button
                onClick={() => handleSimulateAlert("REGIME_CHANGE", "CRITICAL")}
                disabled={simulating}
                className="px-2.5 py-1 rounded bg-rose-600/20 border border-rose-500/30 text-rose-300 text-[11px] font-medium hover:bg-rose-600/30 transition disabled:opacity-50"
              >
                + Critical Regime
              </button>
            </div>
          </div>

          {/* Alert Cards Feed */}
          <div className="space-y-2.5">
            {alerts.length === 0 ? (
              <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-8 text-center font-mono text-xs text-[var(--text-dim)]">
                No alerts logged for the selected filter.
              </div>
            ) : (
              alerts.map((al) => (
                <div
                  key={al.id}
                  className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3.5 hover:border-white/20 transition font-mono text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5">
                      {al.severity === "CRITICAL" ? (
                        <XCircle className="w-4 h-4 text-rose-400" />
                      ) : al.severity === "WARNING" ? (
                        <AlertTriangle className="w-4 h-4 text-amber-400" />
                      ) : (
                        <Zap className="w-4 h-4 text-sky-400" />
                      )}
                    </div>

                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white">{al.asset_id}</span>
                        <span
                          className={`px-1.5 py-0.2 rounded text-[9px] font-bold border ${getSeverityBadge(
                            al.severity
                          )}`}
                        >
                          {al.severity}
                        </span>
                        <span className="text-[10px] text-[var(--text-dim)] uppercase">
                          {al.alert_type.replace(/_/g, " ")}
                        </span>
                      </div>
                      <p className="text-[11px] text-[var(--text-secondary)] mt-1 leading-normal">
                        {al.message}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0 text-right sm:flex-col sm:items-end">
                    <span className="text-[10px] text-[var(--text-dim)] flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatRelativeTime(al.time)}
                    </span>
                    <span className="text-[9px] text-[var(--text-dim)] hidden sm:block">
                      {new Date(al.time).toLocaleTimeString()} UTC
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Configured Rules & Rule Builder */}
      {activeTab === "RULES" && (
        <div className="space-y-6">
          {/* Rule Builder Panel */}
          <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5">
            <div className="flex items-center gap-2 pb-3 mb-4 border-b border-[var(--border-subtle)]">
              <Plus className="w-4 h-4 text-sky-400" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
                Create New Signal Trigger Rule
              </h3>
            </div>

            <form onSubmit={handleAddRule} className="space-y-4 text-xs font-mono">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="text-[10px] text-[var(--text-dim)] uppercase block mb-1">
                    Rule Name
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. BTC Momentum Spike"
                    value={newRuleName}
                    onChange={(e) => setNewRuleName(e.target.value)}
                    className="w-full px-3 py-1.5 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-[var(--radius-sm)] text-white focus:outline-none focus:border-sky-500"
                  />
                </div>

                <div>
                  <label className="text-[10px] text-[var(--text-dim)] uppercase block mb-1">
                    Trigger Condition
                  </label>
                  <select
                    value={newCondition}
                    onChange={(e) => setNewCondition(e.target.value)}
                    className="w-full px-3 py-1.5 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-[var(--radius-sm)] text-white focus:outline-none"
                  >
                    <option value="OPPORTUNITY_SCORE_ABOVE">Opportunity Score &gt;= X</option>
                    <option value="REGIME_CHANGE">Regime Switch (Bull/Bear)</option>
                    <option value="FEED_STALE">Data Feed Lag &gt; X seconds</option>
                    <option value="RISK_FLAG_TRIGGERED">Risk Flag Activated</option>
                  </select>
                </div>

                <div>
                  <label className="text-[10px] text-[var(--text-dim)] uppercase block mb-1">
                    Threshold Value
                  </label>
                  <input
                    type="text"
                    value={newThresholdVal}
                    onChange={(e) => setNewThresholdVal(e.target.value)}
                    className="w-full px-3 py-1.5 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-[var(--radius-sm)] text-white focus:outline-none"
                  />
                </div>
              </div>

              {/* Delivery Channels & Cooldown */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                <div>
                  <label className="text-[10px] text-[var(--text-dim)] uppercase block mb-2">
                    Dispatch Channels
                  </label>
                  <div className="flex flex-wrap gap-4">
                    <label className="flex items-center gap-1.5 cursor-pointer text-white">
                      <input
                        type="checkbox"
                        checked={newChannelTelegram}
                        onChange={(e) => setNewChannelTelegram(e.target.checked)}
                        className="rounded border-[var(--border-subtle)]"
                      />
                      <span>Telegram Bot</span>
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer text-white">
                      <input
                        type="checkbox"
                        checked={newChannelDiscord}
                        onChange={(e) => setNewChannelDiscord(e.target.checked)}
                        className="rounded border-[var(--border-subtle)]"
                      />
                      <span>Discord Webhook</span>
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer text-white">
                      <input
                        type="checkbox"
                        checked={newChannelEmail}
                        onChange={(e) => setNewChannelEmail(e.target.checked)}
                        className="rounded border-[var(--border-subtle)]"
                      />
                      <span>Email Digest</span>
                    </label>
                  </div>
                </div>

                <div>
                  <label className="text-[10px] text-[var(--text-dim)] uppercase block mb-1">
                    Cooldown Window: {newCooldown} Minutes
                  </label>
                  <input
                    type="range"
                    min={15}
                    max={360}
                    step={15}
                    value={newCooldown}
                    onChange={(e) => setNewCooldown(Number(e.target.value))}
                    className="w-full"
                  />
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  type="submit"
                  className="px-4 py-2 bg-sky-600 hover:bg-sky-500 rounded-[var(--radius-sm)] text-white text-xs font-semibold transition"
                >
                  Create Alert Rule
                </button>
              </div>
            </form>
          </div>

          {/* Active Rules List */}
          <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] overflow-hidden font-mono text-xs">
            <div className="p-3.5 border-b border-[var(--border-subtle)] flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
                Active Trigger Rules ({rules.length} configured)
              </h3>
              <span className="text-[10px] text-[var(--text-dim)]">
                Section 7.5 Alert Specification
              </span>
            </div>

            <div className="divide-y divide-[var(--border-subtle)]">
              {rules.map((r) => (
                <div
                  key={r.id}
                  className="p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-[var(--bg-card)]/40 transition"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-white">{r.name}</span>
                      <span
                        className={`px-1.5 py-0.2 rounded text-[9px] font-bold ${
                          r.is_active
                            ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                            : "bg-slate-700/50 text-slate-400"
                        }`}
                      >
                        {r.is_active ? "ENABLED" : "MUTED"}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-[10px] text-[var(--text-secondary)] mt-1">
                      <span>Condition: {r.threshold}</span>
                      <span>•</span>
                      <span>Cooldown: {r.cooldown_minutes}m</span>
                      <span>•</span>
                      <span>Channels: {r.channels.join(", ")}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => toggleRule(r.id)}
                      className={`px-2.5 py-1 rounded text-[11px] font-semibold transition ${
                        r.is_active
                          ? "bg-amber-600/20 text-amber-300 hover:bg-amber-600/30 border border-amber-500/30"
                          : "bg-emerald-600/20 text-emerald-300 hover:bg-emerald-600/30 border border-emerald-500/30"
                      }`}
                    >
                      {r.is_active ? "Mute" : "Enable"}
                    </button>
                    <button
                      onClick={() => deleteRule(r.id)}
                      className="p-1.5 rounded text-[var(--text-dim)] hover:text-rose-400 hover:bg-[var(--bg-card)] transition"
                      title="Delete rule"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Dispatch Channels */}
      {activeTab === "CHANNELS" && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
          {/* Telegram */}
          <div className="p-4 rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-2 mb-3 border-b border-[var(--border-subtle)]">
                <span className="font-bold text-white flex items-center gap-1.5">
                  <Smartphone className="w-4 h-4 text-sky-400" />
                  Telegram Bot Dispatch
                </span>
                <span className="px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 text-[9px] font-bold">
                  ACTIVE
                </span>
              </div>
              <p className="text-[11px] text-[var(--text-muted)] mb-3">
                Direct pushes for alpha breakouts and urgent risk notices.
              </p>
              <div className="space-y-2">
                <div>
                  <span className="text-[10px] text-[var(--text-dim)] block">Bot Token</span>
                  <span className="text-[11px] text-white">•••••••••••••:AAG7X9...</span>
                </div>
                <div>
                  <span className="text-[10px] text-[var(--text-dim)] block">Chat ID</span>
                  <span className="text-[11px] text-white">@crypto_quant_dispatch</span>
                </div>
              </div>
            </div>

            <button
              onClick={() => handleSimulateAlert("TELEGRAM_TEST", "INFO")}
              className="mt-4 w-full py-1.5 rounded bg-[var(--bg-card)] hover:bg-white/10 border border-[var(--border-subtle)] text-white text-[11px] transition"
            >
              Test Telegram Ping
            </button>
          </div>

          {/* Discord */}
          <div className="p-4 rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-2 mb-3 border-b border-[var(--border-subtle)]">
                <span className="font-bold text-white flex items-center gap-1.5">
                  <MessageSquare className="w-4 h-4 text-indigo-400" />
                  Discord Webhook
                </span>
                <span className="px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 text-[9px] font-bold">
                  ACTIVE
                </span>
              </div>
              <p className="text-[11px] text-[var(--text-muted)] mb-3">
                Embed cards formatted with markdown and risk levels into your trading channel.
              </p>
              <div>
                <span className="text-[10px] text-[var(--text-dim)] block">Webhook URL</span>
                <span className="text-[11px] text-white truncate block">
                  https://discord.com/api/webhooks/12...
                </span>
              </div>
            </div>

            <button
              onClick={() => handleSimulateAlert("DISCORD_TEST", "INFO")}
              className="mt-4 w-full py-1.5 rounded bg-[var(--bg-card)] hover:bg-white/10 border border-[var(--border-subtle)] text-white text-[11px] transition"
            >
              Test Discord Ping
            </button>
          </div>

          {/* Email Digest */}
          <div className="p-4 rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-2 mb-3 border-b border-[var(--border-subtle)]">
                <span className="font-bold text-white flex items-center gap-1.5">
                  <Mail className="w-4 h-4 text-amber-400" />
                  Email Digest
                </span>
                <span className="px-1.5 py-0.2 rounded bg-slate-700/50 text-slate-300 text-[9px] font-bold">
                  DAILY
                </span>
              </div>
              <p className="text-[11px] text-[var(--text-muted)] mb-3">
                Daily summary of macro regime changes, top sector rotations, and risk audits.
              </p>
              <div>
                <span className="text-[10px] text-[var(--text-dim)] block">Recipient</span>
                <span className="text-[11px] text-white">researcher@quant-desk.internal</span>
              </div>
            </div>

            <button
              onClick={() => handleSimulateAlert("EMAIL_DIGEST_TEST", "INFO")}
              className="mt-4 w-full py-1.5 rounded bg-[var(--bg-card)] hover:bg-white/10 border border-[var(--border-subtle)] text-white text-[11px] transition"
            >
              Test Email Dispatch
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
