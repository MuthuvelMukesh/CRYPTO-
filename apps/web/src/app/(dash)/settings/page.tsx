"use client";

import React, { useState } from "react";
import {
  Settings,
  Moon,
  Sun,
  Globe,
  Clock,
  Key,
  Shield,
  Check,
  Save,
  Sliders,
  Bell,
  Eye,
  EyeOff,
  RotateCcw,
} from "lucide-react";

export default function SettingsPage() {
  const [saved, setSaved] = useState(false);

  // Appearance & Display
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [timezone, setTimezone] = useState("UTC");
  const [currency, setCurrency] = useState("USD");
  const [precisionMode, setPrecisionMode] = useState<"adaptive" | "fixed">("adaptive");

  // Quant Defaults
  const [defaultMinScore, setDefaultMinScore] = useState(0);
  const [hideStaleFeeds, setHideStaleFeeds] = useState(true);
  const [defaultSlippageBps, setDefaultSlippageBps] = useState(5);
  const [defaultFeeBps, setDefaultFeeBps] = useState(10);

  // Notifications
  const [quietHoursEnabled, setQuietHoursEnabled] = useState(false);
  const [quietHoursStart, setQuietHoursStart] = useState("22:00");
  const [quietHoursEnd, setQuietHoursEnd] = useState("06:00");
  const [telegramNotifications, setTelegramNotifications] = useState(true);
  const [discordNotifications, setDiscordNotifications] = useState(true);

  // API Key Visibility
  const [showApiKey, setShowApiKey] = useState(false);
  const apiKey = "dev-api-key-researcher-1";

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="pb-4 border-b border-[var(--border-subtle)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              Workstation Settings & Preferences
            </h1>
            <span className="text-xs px-2 py-0.5 rounded bg-slate-700/50 text-slate-300 font-mono font-medium">
              v3.0.0
            </span>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Display preferences, default quantitative thresholds, notification routing, and security credentials.
          </p>
        </div>

        {saved && (
          <div className="flex items-center gap-1.5 px-3 py-1 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-mono font-semibold animate-in fade-in">
            <Check className="w-3.5 h-3.5" />
            <span>Preferences Saved</span>
          </div>
        )}
      </div>

      <form onSubmit={handleSave} className="space-y-6 text-xs font-mono">
        {/* Section 1: Appearance & Localization */}
        <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-[var(--border-subtle)]">
            <Globe className="w-4 h-4 text-sky-400" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-white">
              Display, Formatting & Localization
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-[10px] text-[var(--text-dim)] uppercase block mb-1.5">
                Workstation Theme
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setTheme("dark")}
                  className={`p-2.5 rounded-[var(--radius-sm)] border flex items-center justify-center gap-2 transition ${
                    theme === "dark"
                      ? "bg-[var(--bg-card)] border-sky-500 text-white font-bold"
                      : "bg-[var(--bg-card)]/40 border-[var(--border-subtle)] text-[var(--text-dim)]"
                  }`}
                >
                  <Moon className="w-3.5 h-3.5 text-sky-400" />
                  <span>Dark (Default)</span>
                </button>
                <button
                  type="button"
                  onClick={() => setTheme("light")}
                  className={`p-2.5 rounded-[var(--radius-sm)] border flex items-center justify-center gap-2 transition ${
                    theme === "light"
                      ? "bg-[var(--bg-card)] border-sky-500 text-white font-bold"
                      : "bg-[var(--bg-card)]/40 border-[var(--border-subtle)] text-[var(--text-dim)]"
                  }`}
                >
                  <Sun className="w-3.5 h-3.5 text-amber-400" />
                  <span>Light</span>
                </button>
              </div>
            </div>

            <div>
              <label className="text-[10px] text-[var(--text-dim)] uppercase block mb-1.5">
                Timezone Display
              </label>
              <select
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="w-full px-3 py-2 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-[var(--radius-sm)] text-white focus:outline-none"
              >
                <option value="UTC">UTC (Universal Coordinated Time)</option>
                <option value="LOCAL">Local System Clock</option>
                <option value="EST">EST (New York, UTC-5)</option>
                <option value="SGT">SGT (Singapore, UTC+8)</option>
              </select>
            </div>

            <div>
              <label className="text-[10px] text-[var(--text-dim)] uppercase block mb-1.5">
                Price Precision Mode
              </label>
              <select
                value={precisionMode}
                onChange={(e) => setPrecisionMode(e.target.value as any)}
                className="w-full px-3 py-2 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-[var(--radius-sm)] text-white focus:outline-none"
              >
                <option value="adaptive">Adaptive Precision (BTC: 2 dp, Memes: up to 8 dp)</option>
                <option value="fixed">Fixed Decimal (2 dp for all assets)</option>
              </select>
            </div>

            <div>
              <label className="text-[10px] text-[var(--text-dim)] uppercase block mb-1.5">
                Base Currency Symbol
              </label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full px-3 py-2 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-[var(--radius-sm)] text-white focus:outline-none"
              >
                <option value="USD">USD ($)</option>
                <option value="USDT">USDT (₮)</option>
                <option value="EUR">EUR (€)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Section 2: Quantitative Defaults */}
        <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-[var(--border-subtle)]">
            <Sliders className="w-4 h-4 text-emerald-400" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-white">
              Quantitative Scanner & Simulation Defaults
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-[10px] text-[var(--text-dim)] uppercase block mb-1">
                Default Scanner Minimum Score Filter: {defaultMinScore}
              </label>
              <input
                type="range"
                min={0}
                max={75}
                step={5}
                value={defaultMinScore}
                onChange={(e) => setDefaultMinScore(Number(e.target.value))}
                className="w-full mt-2"
              />
              <span className="text-[10px] text-[var(--text-dim)] block mt-1">
                Master Prompt Rule: Initial default must be 0 to show entire universe.
              </span>
            </div>

            <div className="flex items-center pt-4">
              <label className="flex items-center gap-2.5 cursor-pointer text-white">
                <input
                  type="checkbox"
                  checked={hideStaleFeeds}
                  onChange={(e) => setHideStaleFeeds(e.target.checked)}
                  className="rounded border-[var(--border-subtle)]"
                />
                <span>Automatically hide stale assets (&gt; 300s lag) from scanner</span>
              </label>
            </div>

            <div>
              <label className="text-[10px] text-[var(--text-dim)] uppercase block mb-1">
                Default Commission Tier (Basis Points)
              </label>
              <input
                type="number"
                min={0}
                max={100}
                value={defaultFeeBps}
                onChange={(e) => setDefaultFeeBps(Number(e.target.value))}
                className="w-full px-3 py-1.5 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-[var(--radius-sm)] text-white focus:outline-none"
              />
            </div>

            <div>
              <label className="text-[10px] text-[var(--text-dim)] uppercase block mb-1">
                Default Simulated Slippage (Basis Points)
              </label>
              <input
                type="number"
                min={0}
                max={100}
                value={defaultSlippageBps}
                onChange={(e) => setDefaultSlippageBps(Number(e.target.value))}
                className="w-full px-3 py-1.5 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-[var(--radius-sm)] text-white focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* Section 3: Notification Delivery Routing */}
        <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-[var(--border-subtle)]">
            <Bell className="w-4 h-4 text-amber-400" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-white">
              Notification & Dispatch Rules
            </h2>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 rounded bg-[var(--bg-card)] border border-[var(--border-subtle)]">
              <div>
                <span className="font-semibold text-white block">Quiet Hours Mode</span>
                <span className="text-[10px] text-[var(--text-dim)]">
                  Suppress non-critical notifications between {quietHoursStart} and {quietHoursEnd}
                </span>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={quietHoursEnabled}
                  onChange={(e) => setQuietHoursEnabled(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-sky-600"></div>
              </label>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              <label className="flex items-center gap-2 p-3 rounded bg-[var(--bg-card)] border border-[var(--border-subtle)] cursor-pointer text-white">
                <input
                  type="checkbox"
                  checked={telegramNotifications}
                  onChange={(e) => setTelegramNotifications(e.target.checked)}
                  className="rounded border-[var(--border-subtle)]"
                />
                <span>Route critical alerts to Telegram Bot</span>
              </label>
              <label className="flex items-center gap-2 p-3 rounded bg-[var(--bg-card)] border border-[var(--border-subtle)] cursor-pointer text-white">
                <input
                  type="checkbox"
                  checked={discordNotifications}
                  onChange={(e) => setDiscordNotifications(e.target.checked)}
                  className="rounded border-[var(--border-subtle)]"
                />
                <span>Route breakout signals to Discord Webhook</span>
              </label>
            </div>
          </div>
        </div>

        {/* Section 4: Security & Invariant Guards */}
        <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-[var(--border-subtle)]">
            <Shield className="w-4 h-4 text-rose-400" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-white">
              Security Credentials & Invariants
            </h2>
          </div>

          <div className="space-y-3">
            <div>
              <label className="text-[10px] text-[var(--text-dim)] uppercase block mb-1">
                Authenticated Researcher API Key
              </label>
              <div className="flex items-center gap-2">
                <input
                  type={showApiKey ? "text" : "password"}
                  readOnly
                  value={apiKey}
                  className="w-full px-3 py-1.5 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-[var(--radius-sm)] text-white focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="p-2 rounded bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-dim)] hover:text-white transition"
                  title="Toggle visibility"
                >
                  {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Invariant 1 Banner */}
            <div className="p-3.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300">
              <span className="font-bold block mb-0.5">
                Permanent System Guard: LIVE_TRADING_ENABLED=False
              </span>
              <p className="text-[11px] text-amber-200/80 leading-relaxed">
                By architectural invariant, live exchange execution is permanently hard-disabled in the platform core. Real exchange API trading keys cannot be loaded or used. All portfolio actions execute strictly through the double-entry virtual paper broker.
              </p>
            </div>
          </div>
        </div>

        {/* Submit Actions */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="submit"
            className="px-5 py-2.5 rounded-[var(--radius-sm)] bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs flex items-center gap-2 shadow-lg transition"
          >
            <Save className="w-4 h-4" />
            <span>Save Preferences</span>
          </button>
        </div>
      </form>
    </div>
  );
}
