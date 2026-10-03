"use client";

import React, { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
  FlaskConical,
  Play,
  Settings2,
  Sliders,
  ShieldAlert,
  Info,
  Layers,
  Calendar,
  DollarSign,
  Percent,
} from "lucide-react";

import { apiClient } from "@/lib/api/client";

const backtestFormSchema = z.object({
  strategy_name: z.string().min(1, "Strategy is required"),
  symbols: z.string().min(1, "At least one symbol is required"),
  start_date: z.string().min(1, "Start date is required"),
  end_date: z.string().min(1, "End date is required"),
  initial_capital: z.number().min(1000, "Minimum capital is $1,000"),
  maker_fee_bps: z.number().min(0, "Maker fee must be >= 0"),
  taker_fee_bps: z.number().min(0, "Taker fee must be >= 0"),
  slippage_model: z.enum(["fixed", "market_impact"]),
  fixed_slippage_bps: z.number().min(0),
  impact_gamma: z.number().min(0),
  benchmark_symbol: z.string().min(1),
  max_open_positions: z.number().min(1).max(50),
  max_position_weight: z.number().min(0.01).max(1.0),
  point_in_time_universe: z.boolean(),
});

export type BacktestFormData = z.infer<typeof backtestFormSchema>;

interface StrategyInfo {
  name: string;
  version: string;
  description: string;
  default_parameters: Record<string, any>;
}

interface BacktestFormProps {
  onSubmit: (data: any) => void;
  submitting?: boolean;
  className?: string;
}

export function BacktestForm({
  onSubmit,
  submitting = false,
  className = "",
}: BacktestFormProps) {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [loadingStrategies, setLoadingStrategies] = useState(true);

  // Defaults: past 90 days
  const now = new Date();
  const past90d = new Date(now.getTime() - 90 * 86400000);

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<BacktestFormData>({
    resolver: zodResolver(backtestFormSchema),
    defaultValues: {
      strategy_name: "momentum_waterfall",
      symbols: "BTC, ETH, SOL, AVAX, LINK, DOGE",
      start_date: past90d.toISOString().split("T")[0],
      end_date: now.toISOString().split("T")[0],
      initial_capital: 100000,
      maker_fee_bps: 2.0,
      taker_fee_bps: 5.0,
      slippage_model: "market_impact",
      fixed_slippage_bps: 5.0,
      impact_gamma: 0.1,
      benchmark_symbol: "BTC",
      max_open_positions: 10,
      max_position_weight: 0.25,
      point_in_time_universe: true,
    },
  });

  const selectedStrategy = watch("strategy_name");

  useEffect(() => {
    async function loadStrategies() {
      try {
        const res = await apiClient.GET("/api/v1/backtests/strategies");
        if (res.data && Array.isArray(res.data)) {
          setStrategies(res.data as StrategyInfo[]);
          if (res.data[0]) {
            setValue("strategy_name", res.data[0].name);
          }
        }
      } catch {
        // Fallback default strategies list
        setStrategies([
          {
            name: "momentum_waterfall",
            version: "v3.0.0",
            description: "Multi-factor quantitative momentum waterfall with dynamic risk deductions.",
            default_parameters: {},
          },
          {
            name: "trend_regime_breakout",
            version: "v3.0.0",
            description: "Trend following regime filter with volatility-adjusted ATR stops.",
            default_parameters: {},
          },
          {
            name: "cross_sectional_reversal",
            version: "v3.0.0",
            description: "High-frequency mean reversion on extreme factor decile divergences.",
            default_parameters: {},
          },
        ]);
      } finally {
        setLoadingStrategies(false);
      }
    }
    loadStrategies();
  }, [setValue]);

  const onFormSubmit = (values: BacktestFormData) => {
    const symbolList = values.symbols
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);

    const payload = {
      strategy_name: values.strategy_name,
      symbols: symbolList,
      start_date: new Date(values.start_date).toISOString(),
      end_date: new Date(`${values.end_date}T23:59:59Z`).toISOString(),
      initial_capital: values.initial_capital,
      maker_fee_bps: values.maker_fee_bps,
      taker_fee_bps: values.taker_fee_bps,
      slippage_model: values.slippage_model,
      fixed_slippage_bps: values.fixed_slippage_bps,
      impact_gamma: values.impact_gamma,
      benchmark_symbol: values.benchmark_symbol.toUpperCase(),
      max_open_positions: values.max_open_positions,
      max_position_weight: values.max_position_weight,
      point_in_time_universe: values.point_in_time_universe,
      parameters: {},
    };

    onSubmit(payload);
  };

  const currentStrategyInfo = strategies.find((s) => s.name === selectedStrategy);

  return (
    <form
      onSubmit={handleSubmit(onFormSubmit)}
      className={`rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 flex flex-col space-y-5 ${className}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-[var(--border-subtle)]">
        <div className="flex items-center gap-2">
          <FlaskConical className="w-4 h-4 text-purple-400" />
          <h2 className="text-sm font-semibold uppercase tracking-wider text-white">
            Backtest Simulation Setup
          </h2>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-bold">
          STRICT T+1 FILLS
        </span>
      </div>

      {/* Grid Inputs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-xs font-mono">
        {/* Strategy Selector */}
        <div>
          <label className="text-[10px] uppercase text-[var(--text-dim)] block mb-1">
            Quantitative Strategy
          </label>
          <select
            {...register("strategy_name")}
            className="w-full px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-white focus:outline-hidden focus:border-purple-500"
          >
            {strategies.map((strat) => (
              <option key={strat.name} value={strat.name}>
                {strat.name} ({strat.version})
              </option>
            ))}
          </select>
          {currentStrategyInfo && (
            <span className="text-[10px] text-[var(--text-dim)] mt-1 block truncate">
              {currentStrategyInfo.description}
            </span>
          )}
        </div>

        {/* Universe Symbols */}
        <div>
          <label className="text-[10px] uppercase text-[var(--text-dim)] block mb-1">
            Simulated Universe (Symbols)
          </label>
          <input
            type="text"
            {...register("symbols")}
            placeholder="BTC, ETH, SOL, AVAX"
            className="w-full px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-white focus:outline-hidden focus:border-purple-500"
          />
          {errors.symbols && (
            <span className="text-rose-400 text-[10px]">{errors.symbols.message}</span>
          )}
        </div>

        {/* Starting Capital */}
        <div>
          <label className="text-[10px] uppercase text-[var(--text-dim)] block mb-1">
            Starting Capital ($)
          </label>
          <input
            type="number"
            step="1000"
            {...register("initial_capital", { valueAsNumber: true })}
            className="w-full px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-white focus:outline-hidden focus:border-purple-500"
          />
          {errors.initial_capital && (
            <span className="text-rose-400 text-[10px]">{errors.initial_capital.message}</span>
          )}
        </div>

        {/* Date Range: Start Date */}
        <div>
          <label className="text-[10px] uppercase text-[var(--text-dim)] block mb-1">
            Start Date (UTC)
          </label>
          <input
            type="date"
            {...register("start_date")}
            className="w-full px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-white focus:outline-hidden focus:border-purple-500"
          />
        </div>

        {/* Date Range: End Date */}
        <div>
          <label className="text-[10px] uppercase text-[var(--text-dim)] block mb-1">
            End Date (UTC)
          </label>
          <input
            type="date"
            {...register("end_date")}
            className="w-full px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-white focus:outline-hidden focus:border-purple-500"
          />
        </div>

        {/* Benchmark Asset */}
        <div>
          <label className="text-[10px] uppercase text-[var(--text-dim)] block mb-1">
            Alpha Benchmark Asset
          </label>
          <input
            type="text"
            {...register("benchmark_symbol")}
            className="w-full px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-white focus:outline-hidden focus:border-purple-500"
          />
        </div>

        {/* Maker / Taker Fees */}
        <div>
          <label className="text-[10px] uppercase text-[var(--text-dim)] block mb-1">
            Taker Fee (bps)
          </label>
          <input
            type="number"
            step="0.5"
            {...register("taker_fee_bps", { valueAsNumber: true })}
            className="w-full px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-white focus:outline-hidden focus:border-purple-500"
          />
        </div>

        {/* Slippage Model */}
        <div>
          <label className="text-[10px] uppercase text-[var(--text-dim)] block mb-1">
            Slippage Micro-Structure
          </label>
          <select
            {...register("slippage_model")}
            className="w-full px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-white focus:outline-hidden focus:border-purple-500"
          >
            <option value="market_impact">Square-Root Market Impact</option>
            <option value="fixed">Fixed Basis Points</option>
          </select>
        </div>

        {/* Position Weight Limit */}
        <div>
          <label className="text-[10px] uppercase text-[var(--text-dim)] block mb-1">
            Max Single Position Weight
          </label>
          <select
            {...register("max_position_weight", { valueAsNumber: true })}
            className="w-full px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-white focus:outline-hidden focus:border-purple-500"
          >
            <option value={0.15}>15% (Defensive)</option>
            <option value={0.25}>25% (Standard)</option>
            <option value={0.5}>50% (Concentrated)</option>
          </select>
        </div>
      </div>

      {/* Assumptions Summary Box (Required by Section 7.5) */}
      <div className="rounded-[var(--radius-sm)] bg-[var(--bg-card)] p-3 border border-[var(--border-subtle)] text-xs font-mono space-y-1 text-[var(--text-muted)]">
        <span className="text-white font-semibold flex items-center gap-1.5">
          <Info className="w-3.5 h-3.5 text-sky-400" />
          Engine Execution Assumptions Summary
        </span>
        <ul className="list-disc pl-4 space-y-0.5 text-[11px]">
          <li><strong>No Look-Ahead (Phase 1):</strong> Signals evaluated at bar <em>t</em> close fill at bar <em>t+1</em> open.</li>
          <li><strong>Execution Realism:</strong> Stop triggers gap to bar open; take-profit executes at target or gap open.</li>
          <li><strong>Survivorship Bias Guard:</strong> Point-in-time universe prevents future-inclusion leakage.</li>
        </ul>
      </div>

      {/* Submit Trigger - Never auto-run on load */}
      <div className="flex items-center justify-between pt-2 border-t border-[var(--border-subtle)]">
        <span className="text-[11px] font-mono text-[var(--text-dim)]">
          Runs asynchronously in backend worker with progress tracking.
        </span>

        <button
          type="submit"
          disabled={submitting}
          className="flex items-center gap-2 px-5 py-2 rounded-[var(--radius-sm)] bg-purple-600 hover:bg-purple-500 text-white font-mono text-xs font-bold transition disabled:opacity-50 shadow-lg shadow-purple-600/20"
        >
          <Play className={`w-3.5 h-3.5 ${submitting ? "animate-spin" : ""}`} />
          <span>{submitting ? "Dispatching Job..." : "Launch Backtest Job"}</span>
        </button>
      </div>
    </form>
  );
}
