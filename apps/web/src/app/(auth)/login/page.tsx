"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ShieldAlert, Terminal, Lock, Key, ArrowRight } from "lucide-react";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get("redirect") || "/scanner";

  const [mode, setMode] = useState<"creds" | "api_key">("creds");
  const [username, setUsername] = useState("researcher");
  const [password, setPassword] = useState("quant-v3-secret");
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const payload =
        mode === "creds"
          ? { username, password }
          : { apiKey };

      const res = await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Authentication failed");
      }

      router.push(redirect);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-[var(--radius-lg)] p-8 shadow-2xl relative z-10">
      {/* Terminal Header */}
      <div className="flex items-center space-x-3 mb-6">
        <div className="w-10 h-10 rounded-[var(--radius-md)] bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
          <Terminal className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
            QUANT LAB <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-mono">v3.0</span>
          </h1>
          <p className="text-xs text-[var(--text-muted)]">Research & Paper-Trading Workstation</p>
        </div>
      </div>

      {/* Safety Invariant Notice */}
      <div className="mb-6 p-3 rounded-[var(--radius-sm)] bg-amber-500/10 border border-amber-500/25 flex items-start gap-2.5 text-xs text-amber-200">
        <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-amber-300">Live Trading Hard-Disabled:</span> Market data & backtesting only. No real orders are ever routed.
        </div>
      </div>

      {/* Mode Selector Tabs */}
      <div className="grid grid-cols-2 gap-2 mb-6 bg-[var(--bg-card)] p-1 rounded-[var(--radius-sm)] border border-[var(--border-subtle)]">
        <button
          type="button"
          onClick={() => setMode("creds")}
          className={`py-1.5 text-xs font-medium rounded transition flex items-center justify-center gap-1.5 ${
            mode === "creds"
              ? "bg-[var(--bg-surface)] text-white shadow-sm"
              : "text-[var(--text-muted)] hover:text-white"
          }`}
        >
          <Lock className="w-3.5 h-3.5" /> Researcher Login
        </button>
        <button
          type="button"
          onClick={() => setMode("api_key")}
          className={`py-1.5 text-xs font-medium rounded transition flex items-center justify-center gap-1.5 ${
            mode === "api_key"
              ? "bg-[var(--bg-surface)] text-white shadow-sm"
              : "text-[var(--text-muted)] hover:text-white"
          }`}
        >
          <Key className="w-3.5 h-3.5" /> API Key
        </button>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-2.5 rounded bg-rose-500/10 border border-rose-500/25 text-rose-300 text-xs">
            {error}
          </div>
        )}

        {mode === "creds" ? (
          <>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
                User Handle
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full px-3 py-2 text-sm bg-[var(--bg-card)] border border-[var(--border-strong)] rounded-[var(--radius-sm)] text-white focus:outline-none focus:border-indigo-400 font-mono"
                placeholder="researcher"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
                Workstation Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-3 py-2 text-sm bg-[var(--bg-card)] border border-[var(--border-strong)] rounded-[var(--radius-sm)] text-white focus:outline-none focus:border-indigo-400 font-mono"
                placeholder="••••••••••••"
              />
            </div>
          </>
        ) : (
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
              Session API Key
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              required
              className="w-full px-3 py-2 text-sm bg-[var(--bg-card)] border border-[var(--border-strong)] rounded-[var(--radius-sm)] text-white focus:outline-none focus:border-indigo-400 font-mono"
              placeholder="dev-api-key-researcher-1"
            />
            <p className="text-[11px] text-[var(--text-dim)] mt-1.5">
              Paste any valid research key (e.g. dev-api-key-researcher-1).
            </p>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full mt-2 py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-[var(--radius-sm)] transition flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/20"
        >
          {loading ? "Authenticating Session..." : "Enter Quant Workstation"}
          {!loading && <ArrowRight className="w-4 h-4" />}
        </button>
      </form>

      <div className="mt-6 pt-4 border-t border-[var(--border-subtle)] text-center text-[11px] text-[var(--text-dim)]">
        Crypto Intelligence Platform v3.0 &bull; Read-Only Market Feed
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center p-4 bg-[var(--bg-base)] text-[var(--text-primary)]">
      <div className="absolute inset-0 bg-gradient-to-b from-indigo-950/20 via-transparent to-transparent pointer-events-none" />
      <Suspense fallback={<div className="w-full max-w-md h-96 rounded-[var(--radius-lg)] bg-[var(--bg-surface)] animate-pulse" />}>
        <LoginForm />
      </Suspense>
    </div>
  );
}
