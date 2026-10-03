"use client";

import React, { useEffect, useRef, useState, useMemo } from "react";
import {
  createChart,
  ColorType,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { Layers, Eye, EyeOff } from "lucide-react";

export interface CandleDataPoint {
  time: string; // ISO string
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface CandleChartProps {
  candles: CandleDataPoint[];
  symbol: string;
  timeframe: string;
  onTimeframeChange?: (tf: string) => void;
  className?: string;
}

function calculateEMA(
  data: { time: UTCTimestamp; close: number }[],
  period: number
): { time: UTCTimestamp; value: number }[] {
  if (data.length < period) return [];
  const k = 2 / (period + 1);
  const emaData: { time: UTCTimestamp; value: number }[] = [];

  let sum = 0;
  for (let i = 0; i < period; i++) {
    sum += data[i]!.close;
  }
  let prevEma = sum / period;
  emaData.push({ time: data[period - 1]!.time, value: prevEma });

  for (let i = period; i < data.length; i++) {
    const currentEma = data[i]!.close * k + prevEma * (1 - k);
    emaData.push({ time: data[i]!.time, value: currentEma });
    prevEma = currentEma;
  }
  return emaData;
}

export function CandleChart({
  candles,
  symbol,
  timeframe,
  onTimeframeChange,
  className = "",
}: CandleChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const ema20SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ema50SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ema200SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  const [showEMA20, setShowEMA20] = useState(true);
  const [showEMA50, setShowEMA50] = useState(true);
  const [showEMA200, setShowEMA200] = useState(true);
  const [hoverData, setHoverData] = useState<{
    time?: string;
    open?: number;
    high?: number;
    low?: number;
    close?: number;
    volume?: number;
  } | null>(null);

  // Parse candles for lightweight-charts
  const chartData = useMemo(() => {
    if (!candles || candles.length === 0) return { candles: [], volumes: [], emaInput: [] };

    // Sort ascending by time
    const sorted = [...candles].sort(
      (a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()
    );

    const formattedCandles: any[] = [];
    const formattedVolumes: any[] = [];
    const emaInput: { time: UTCTimestamp; close: number }[] = [];

    for (const c of sorted) {
      const utcSec = Math.floor(new Date(c.time).getTime() / 1000) as UTCTimestamp;
      const isUp = c.close >= c.open;

      formattedCandles.push({
        time: utcSec,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      });

      formattedVolumes.push({
        time: utcSec,
        value: c.volume,
        color: isUp ? "rgba(16, 185, 129, 0.35)" : "rgba(244, 63, 94, 0.35)",
      });

      emaInput.push({
        time: utcSec,
        close: c.close,
      });
    }

    return {
      candles: formattedCandles,
      volumes: formattedVolumes,
      emaInput,
    };
  }, [candles]);

  useEffect(() => {
    if (!containerRef.current) return;

    // Create chart
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 440,
      layout: {
        background: { type: ColorType.Solid, color: "#0f172a" },
        textColor: "#94a3b8",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(30, 41, 59, 0.6)" },
        horzLines: { color: "rgba(30, 41, 59, 0.6)" },
      },
      crosshair: {
        vertLine: {
          color: "#38bdf8",
          width: 1,
          style: LineStyle.Dashed,
        },
        horzLine: {
          color: "#38bdf8",
          width: 1,
          style: LineStyle.Dashed,
        },
      },
      timeScale: {
        borderColor: "#1e293b",
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: "#1e293b",
        autoScale: true,
      },
    });

    chartRef.current = chart;

    // 1. Candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: "#10b981",
      downColor: "#f43f5e",
      borderVisible: false,
      wickUpColor: "#10b981",
      wickDownColor: "#f43f5e",
    });
    candleSeriesRef.current = candleSeries;

    // 2. Volume series
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });
    volumeSeriesRef.current = volumeSeries;

    // 3. EMA Line Series
    const ema20Series = chart.addLineSeries({
      color: "#38bdf8",
      lineWidth: 1,
      title: "EMA 20",
    });
    ema20SeriesRef.current = ema20Series;

    const ema50Series = chart.addLineSeries({
      color: "#818cf8",
      lineWidth: 1,
      title: "EMA 50",
    });
    ema50SeriesRef.current = ema50Series;

    const ema200Series = chart.addLineSeries({
      color: "#fbbf24",
      lineWidth: 1,
      title: "EMA 200",
    });
    ema200SeriesRef.current = ema200Series;

    // Crosshair handler
    chart.subscribeCrosshairMove((param) => {
      if (
        param.point === undefined ||
        !param.time ||
        param.point.x < 0 ||
        param.point.x > containerRef.current!.clientWidth ||
        param.point.y < 0 ||
        param.point.y > 440
      ) {
        setHoverData(null);
      } else {
        const c = param.seriesData.get(candleSeries) as any;
        const v = param.seriesData.get(volumeSeries) as any;
        if (c) {
          setHoverData({
            time: typeof param.time === "number" ? new Date(param.time * 1000).toUTCString() : String(param.time),
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
            volume: v ? v.value : undefined,
          });
        }
      }
    });

    // Resize observer
    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
        });
      }
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  // Update Data
  useEffect(() => {
    if (!chartRef.current || !candleSeriesRef.current || !volumeSeriesRef.current) return;

    candleSeriesRef.current.setData(chartData.candles);
    volumeSeriesRef.current.setData(chartData.volumes);

    // EMA series
    if (ema20SeriesRef.current) {
      if (showEMA20) {
        const ema20 = calculateEMA(chartData.emaInput, 20);
        ema20SeriesRef.current.setData(ema20);
      } else {
        ema20SeriesRef.current.setData([]);
      }
    }

    if (ema50SeriesRef.current) {
      if (showEMA50) {
        const ema50 = calculateEMA(chartData.emaInput, 50);
        ema50SeriesRef.current.setData(ema50);
      } else {
        ema50SeriesRef.current.setData([]);
      }
    }

    if (ema200SeriesRef.current) {
      if (showEMA200) {
        const ema200 = calculateEMA(chartData.emaInput, 200);
        ema200SeriesRef.current.setData(ema200);
      } else {
        ema200SeriesRef.current.setData([]);
      }
    }

    chartRef.current.timeScale().fitContent();
  }, [chartData, showEMA20, showEMA50, showEMA200]);

  return (
    <div className={`rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 flex flex-col ${className}`}>
      {/* Chart Top Controls */}
      <div className="flex flex-wrap items-center justify-between pb-3 mb-2 border-b border-[var(--border-subtle)] gap-2">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 font-mono text-xs font-bold text-white">
            <Layers className="w-4 h-4 text-sky-400" />
            <span>{symbol}/USDT</span>
          </div>

          {/* Timeframe selector */}
          <div className="flex items-center rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] p-0.5 text-xs font-mono">
            {["1h", "4h", "1d"].map((tf) => (
              <button
                key={tf}
                type="button"
                onClick={() => onTimeframeChange?.(tf)}
                className={`px-2 py-0.5 rounded-[var(--radius-sm)] uppercase transition ${
                  timeframe.toLowerCase() === tf
                    ? "bg-sky-500/20 text-sky-300 font-semibold"
                    : "text-[var(--text-muted)] hover:text-white"
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>

        {/* EMA Indicator Toggles */}
        <div className="flex items-center gap-2 text-[11px] font-mono">
          <button
            type="button"
            onClick={() => setShowEMA20(!showEMA20)}
            className={`flex items-center gap-1 px-2 py-0.5 rounded border transition ${
              showEMA20
                ? "bg-sky-500/15 border-sky-500/30 text-sky-400"
                : "border-[var(--border-subtle)] text-[var(--text-dim)]"
            }`}
          >
            <span className="w-2 h-0.5 bg-sky-400 rounded-full" />
            <span>EMA 20</span>
          </button>

          <button
            type="button"
            onClick={() => setShowEMA50(!showEMA50)}
            className={`flex items-center gap-1 px-2 py-0.5 rounded border transition ${
              showEMA50
                ? "bg-indigo-500/15 border-indigo-500/30 text-indigo-400"
                : "border-[var(--border-subtle)] text-[var(--text-dim)]"
            }`}
          >
            <span className="w-2 h-0.5 bg-indigo-400 rounded-full" />
            <span>EMA 50</span>
          </button>

          <button
            type="button"
            onClick={() => setShowEMA200(!showEMA200)}
            className={`flex items-center gap-1 px-2 py-0.5 rounded border transition ${
              showEMA200
                ? "bg-amber-500/15 border-amber-500/30 text-amber-400"
                : "border-[var(--border-subtle)] text-[var(--text-dim)]"
            }`}
          >
            <span className="w-2 h-0.5 bg-amber-400 rounded-full" />
            <span>EMA 200</span>
          </button>
        </div>
      </div>

      {/* OHLCV Hover Tooltip / Status Display */}
      <div className="flex items-center gap-4 text-xs font-mono text-[var(--text-dim)] mb-1 h-5 overflow-hidden">
        {hoverData ? (
          <>
            <span className="text-[var(--text-secondary)]">{hoverData.time}</span>
            <span>
              O: <strong className="text-white">{hoverData.open?.toFixed(2)}</strong>
            </span>
            <span>
              H: <strong className="text-white">{hoverData.high?.toFixed(2)}</strong>
            </span>
            <span>
              L: <strong className="text-white">{hoverData.low?.toFixed(2)}</strong>
            </span>
            <span>
              C: <strong className="text-white">{hoverData.close?.toFixed(2)}</strong>
            </span>
            {hoverData.volume !== undefined && (
              <span>
                Vol: <strong className="text-white">{hoverData.volume.toLocaleString()}</strong>
              </span>
            )}
          </>
        ) : (
          <span className="text-[11px] text-[var(--text-dim)]">Hover over candles for OHLCV telemetry</span>
        )}
      </div>

      {/* Lightweight Charts Canvas Host */}
      <div ref={containerRef} className="w-full h-[440px] relative" />
    </div>
  );
}
