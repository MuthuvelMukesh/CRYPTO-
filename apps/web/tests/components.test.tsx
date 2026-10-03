import { describe, it, expect, vi } from "vitest";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  DeltaCell,
  ScoreBadge,
  FreshnessDot,
  Sparkline,
  EmptyState,
  ErrorState,
} from "../src/components/data";
import { RegimeBadge } from "../src/components/domain/RegimeBadge";
import { FactorRadarChart } from "../src/components/charts/FactorRadarChart";
import { EquityChart } from "../src/components/charts/EquityChart";
import { FeatureGlossaryTable } from "../src/components/domain/FeatureGlossaryTable";
import { OrderTicketModal } from "../src/components/domain/OrderTicketModal";
import { AccountResetModal } from "../src/components/domain/AccountResetModal";
import { UnderwaterDrawdownChart } from "../src/components/charts/UnderwaterDrawdownChart";
import { BacktestMetricsGrid } from "../src/components/domain/BacktestMetricsGrid";
import { BacktestTradeTable } from "../src/components/domain/BacktestTradeTable";
import { RollingICChart } from "../src/components/charts/RollingICChart";
import { DecileBarChart } from "../src/components/charts/DecileBarChart";
import { DecileTable } from "../src/components/domain/DecileTable";
import { ModelGateAuditCard } from "../src/components/domain/ModelGateAuditCard";
import { MemeDetailDrawer } from "../src/components/domain/MemeDetailDrawer";
import { SectorRotationChart } from "../src/components/charts/SectorRotationChart";

describe("Shared Data Components", () => {
  describe("DeltaCell", () => {
    it("renders positive delta with green color and arrow", () => {
      const { container } = render(<DeltaCell value={4.25} />);
      expect(screen.getByText("+4.25%")).toBeDefined();
      expect(container.textContent).toContain("▲");
      expect((container.firstChild as HTMLElement).className).toContain("text-emerald-400");
    });

    it("renders negative delta with red color and arrow", () => {
      const { container } = render(<DeltaCell value={-2.1} />);
      expect(screen.getByText("-2.10%")).toBeDefined();
      expect(container.textContent).toContain("▼");
      expect((container.firstChild as HTMLElement).className).toContain("text-rose-400");
    });

    it("renders em-dash fallback on null value", () => {
      render(<DeltaCell value={null} />);
      expect(screen.getByText("—")).toBeDefined();
    });
  });

  describe("ScoreBadge", () => {
    it("renders high score with strong tier styling", () => {
      render(<ScoreBadge score={88.4} />);
      expect(screen.getByText("88.4")).toBeDefined();
    });

    it("renders partial data indicator [P] when partialData is true", () => {
      render(<ScoreBadge score={72.0} partialData={true} />);
      expect(screen.getByText("72.0")).toBeDefined();
      expect(screen.getByText("P")).toBeDefined();
    });

    it("renders em-dash on null score", () => {
      render(<ScoreBadge score={null} />);
      expect(screen.getByText("—")).toBeDefined();
    });
  });

  describe("FreshnessDot", () => {
    it("renders fallback em-dash when timestamp is null", () => {
      const { container } = render(<FreshnessDot timestamp={null} showLabel={true} />);
      expect(container.textContent).toContain("—");
    });

    it("renders relative age when timestamp is given", () => {
      const fiveMinsAgo = new Date(Date.now() - 5 * 60 * 1000);
      render(<FreshnessDot timestamp={fiveMinsAgo.toISOString()} showLabel={true} />);
      expect(screen.getByText("5m ago")).toBeDefined();
    });
  });

  describe("Sparkline", () => {
    it("renders SVG curve for valid price data array", () => {
      const { container } = render(<Sparkline data={[100, 105, 102, 110, 115]} />);
      const svg = container.querySelector("svg");
      expect(svg).toBeDefined();
      expect(svg?.querySelector("path")).toBeDefined();
    });

    it("renders em-dash on null data or single point", () => {
      render(<Sparkline data={null} />);
      expect(screen.getByText("—")).toBeDefined();

      const { container } = render(<Sparkline data={[100]} />);
      expect(container.textContent).toContain("—");
    });
  });

  describe("EmptyState", () => {
    it("renders title, description and triggers action", () => {
      const handleClick = vi.fn();
      render(
        <EmptyState
          title="No Data Available"
          description="Check back later."
          actionLabel="Refresh Now"
          onAction={handleClick}
        />
      );

      expect(screen.getByText("No Data Available")).toBeDefined();
      expect(screen.getByText("Check back later.")).toBeDefined();

      const button = screen.getByText("Refresh Now");
      fireEvent.click(button);
      expect(handleClick).toHaveBeenCalledTimes(1);
    });
  });

  describe("ErrorState", () => {
    it("renders RFC 7807 problem details and triggers retry", () => {
      const handleRetry = vi.fn();
      render(
        <ErrorState
          problem={{
            type: "https://httpstatuses.com/503",
            title: "Service Unavailable",
            status: 503,
            detail: "CCXT exchange rate-limited.",
          }}
          onRetry={handleRetry}
        />
      );

      expect(screen.getByText("Service Unavailable")).toBeDefined();
      expect(screen.getByText("HTTP 503")).toBeDefined();
      expect(screen.getByText("CCXT exchange rate-limited.")).toBeDefined();

      const retryBtn = screen.getByText("Retry Request");
      fireEvent.click(retryBtn);
      expect(handleRetry).toHaveBeenCalledTimes(1);
    });
  });

  describe("RegimeBadge", () => {
    it("renders RISK_ON with positive styling and confidence", () => {
      const { container } = render(
        <RegimeBadge regime="RISK_ON" confidence={0.88} />
      );
      expect(screen.getByText("RISK-ON")).toBeDefined();
      expect(screen.getByText("88%")).toBeDefined();
      expect(container.firstChild).toBeDefined();
      expect((container.firstChild as HTMLElement).className).toContain("text-[var(--color-positive)]");
    });

    it("renders RISK_OFF with negative styling and confidence", () => {
      const { container } = render(
        <RegimeBadge regime="RISK_OFF" confidence={0.75} />
      );
      expect(screen.getByText("RISK-OFF")).toBeDefined();
      expect(screen.getByText("75%")).toBeDefined();
      expect((container.firstChild as HTMLElement).className).toContain("text-[var(--color-negative)]");
    });

    it("renders NEUTRAL with info styling", () => {
      const { container } = render(
        <RegimeBadge regime="NEUTRAL" confidence={0.5} />
      );
      expect(screen.getByText("NEUTRAL")).toBeDefined();
      expect(screen.getByText("50%")).toBeDefined();
      expect((container.firstChild as HTMLElement).className).toContain("text-[var(--color-info)]");
    });

    it("renders accessible role and aria-label", () => {
      render(<RegimeBadge regime="RISK_ON" confidence={0.9} />);
      const badge = screen.getByRole("status");
      expect(badge.getAttribute("aria-label")).toContain("Market Regime: RISK-ON");
      expect(badge.getAttribute("aria-label")).toContain("90%");
    });
  });

  describe("FactorRadarChart", () => {
    it("renders SVG polygon and factor scores", () => {
      render(
        <FactorRadarChart
          trendScore={82}
          momentumScore={75}
          qualityScore={90}
          liquidityScore={65}
          relativeStrengthScore={78}
          opportunityScore={81.5}
        />
      );
      expect(screen.getByText("Factor Radar Profile")).toBeDefined();
      expect(screen.getByText("Net Score: 81.5")).toBeDefined();
      expect(screen.getByText("Trend")).toBeDefined();
      expect(screen.getByText("Momentum")).toBeDefined();
      expect(screen.getByText("Quality")).toBeDefined();
      expect(screen.getByText("Liquidity")).toBeDefined();
      expect(screen.getByText("Rel Strength")).toBeDefined();
    });
  });

  describe("FeatureGlossaryTable", () => {
    it("renders feature metrics and handles category filter", () => {
      render(
        <FeatureGlossaryTable
          features={{
            return_1d: 0.052,
            return_7d: 0.145,
            adx_14: 28.4,
            spread_est_bps: 14.2,
          }}
        />
      );
      expect(screen.getByText("Quantitative Feature Telemetry")).toBeDefined();
      expect(screen.getByText("1D Trailing Return")).toBeDefined();
      expect(screen.getByText("+5.20%")).toBeDefined();
      expect(screen.getByText("28.4")).toBeDefined();

      // Click category tab "Trend"
      const trendTab = screen.getByRole("button", { name: "Trend" });
      fireEvent.click(trendTab);
      expect(screen.getByText("ADX (14)")).toBeDefined();
    });
  });

  describe("OrderTicketModal", () => {
    it("renders paper trading warning and order details", () => {
      render(
        <OrderTicketModal
          symbol="SOL"
          currentPrice={145.5}
          isOpen={true}
          onClose={() => {}}
        />
      );
      expect(screen.getByText("Paper Order Ticket — SOL/USDT")).toBeDefined();
      expect(
        screen.getByText(
          "Paper trading simulation only. No live funds or real exchange keys."
        )
      ).toBeDefined();
      expect(screen.getByText("Reference Price")).toBeDefined();
    });

    it("does not render when isOpen is false", () => {
      const { container } = render(
        <OrderTicketModal
          symbol="SOL"
          currentPrice={145.5}
          isOpen={false}
          onClose={() => {}}
        />
      );
      expect(container.firstChild).toBeNull();
    });
  });

  describe("EquityChart", () => {
    it("renders equity curve with performance metrics", () => {
      render(
        <EquityChart
          data={[
            { time: "2026-10-01T00:00:00Z", equity: 100000, cash: 100000 },
            { time: "2026-10-02T00:00:00Z", equity: 105000, cash: 95000 },
          ]}
          peakEquity={105000}
          currentDrawdown={0}
        />
      );
      expect(screen.getByText("Portfolio Equity Curve")).toBeDefined();
      expect(screen.getByText("+5.00%")).toBeDefined();
      expect(screen.getAllByText("$105,000.00").length).toBeGreaterThan(0);
    });
  });

  describe("AccountResetModal", () => {
    it("requires typed confirmation 'RESET' to enable submit button", () => {
      render(
        <AccountResetModal
          isOpen={true}
          onClose={() => {}}
        />
      );
      expect(screen.getByText("Reset Virtual Paper Account")).toBeDefined();
      const submitBtn = screen.getByRole("button", { name: /Confirm Account Reset/i });
      expect(submitBtn.hasAttribute("disabled")).toBe(true);

      const input = screen.getByPlaceholderText("RESET");
      fireEvent.change(input, { target: { value: "RESET" } });
      expect(submitBtn.hasAttribute("disabled")).toBe(false);
    });
  });

  describe("UnderwaterDrawdownChart", () => {
    it("renders underwater profile and max drawdown", () => {
      render(
        <UnderwaterDrawdownChart
          data={[
            { time: "2026-10-01T00:00:00Z", drawdown_pct: 0 },
            { time: "2026-10-02T00:00:00Z", drawdown_pct: -6.4 },
          ]}
          maxDrawdown={6.4}
        />
      );
      expect(screen.getByText("Underwater Drawdown Profile")).toBeDefined();
      expect(screen.getByText("-6.40%")).toBeDefined();
    });

    it("renders awaiting message when data is insufficient", () => {
      render(<UnderwaterDrawdownChart data={[]} />);
      expect(screen.getByText("Awaiting data")).toBeDefined();
    });
  });

  describe("BacktestMetricsGrid", () => {
    it("renders performance metrics with bootstrap CI and cost stress table", () => {
      render(
        <BacktestMetricsGrid
          totalReturnPct={42.5}
          cagr={18.2}
          sharpeRatio={1.95}
          sortinoRatio={2.45}
          maxDrawdownPct={8.5}
          winRate={0.62}
          profitFactor={1.85}
          benchmarkReturnPct={12.0}
          metrics={{
            sharpe_ci_low: 1.6,
            sharpe_ci_high: 2.3,
          }}
        />
      );
      expect(screen.getAllByText("+42.50%").length).toBeGreaterThan(0);
      expect(screen.getAllByText("1.95").length).toBeGreaterThan(0);
      expect(screen.getByText("CI: [1.60, 2.30]")).toBeDefined();
      expect(screen.getByText("Cost Stress Resilience (1x / 2x / 3x Fees)")).toBeDefined();
      expect(screen.getByText("Regime-Split Performance")).toBeDefined();
    });
  });

  describe("BacktestTradeTable", () => {
    it("renders trade rows and flags low confidence trades", () => {
      render(
        <BacktestTradeTable
          trades={[
            {
              id: "t-1",
              asset_id: "SOL",
              entry_time: "2026-10-01T10:00:00Z",
              exit_time: "2026-10-02T10:00:00Z",
              entry_price: 140.0,
              exit_price: 152.0,
              pnl_usd: 1200.0,
              pnl_pct: 8.57,
              fees_usd: 12.0,
              low_confidence: true,
            },
          ]}
        />
      );
      expect(screen.getByText("Simulated Trade Log (1 fills)")).toBeDefined();
      expect(screen.getAllByText("SOL").length).toBeGreaterThan(0);
      expect(screen.getByText("+$1,200.00")).toBeDefined();
      expect(screen.getByText("+8.57%")).toBeDefined();
      expect(screen.getByText("LOW_CONF")).toBeDefined();
    });
  });

  describe("RollingICChart", () => {
    it("renders rolling IC chart with points and horizon", () => {
      render(
        <RollingICChart
          points={[
            { date: "2026-10-01", pearson_ic: 0.15, spearman_ic: 0.18, sample_size: 50 },
            { date: "2026-10-02", pearson_ic: 0.12, spearman_ic: 0.14, sample_size: 50 },
          ]}
          horizon="1d"
        />
      );
      expect(screen.getByText("Rolling Information Coefficient (IC)")).toBeDefined();
      expect(screen.getByText("Horizon: 1D")).toBeDefined();
      expect(screen.getByText("Pearson IC")).toBeDefined();
      expect(screen.getByText("Spearman Rank IC")).toBeDefined();
    });

    it("renders awaiting message when points are empty", () => {
      render(<RollingICChart points={[]} />);
      expect(screen.getByText(/Awaiting Information Coefficient/i)).toBeDefined();
    });
  });

  describe("DecileBarChart", () => {
    it("renders decile bars and monotonicity spread", () => {
      render(
        <DecileBarChart
          deciles={[
            { decile: 1, mean_forward_return_pct: -2.5, sample_size: 35 },
            { decile: 10, mean_forward_return_pct: 4.8, sample_size: 35 },
          ]}
          monotonicitySpreadPct={7.3}
          horizon="1d"
        />
      );
      expect(screen.getByText("Forward Return by Score Decile (D1 – D10)")).toBeDefined();
      expect(screen.getByText("+7.30%")).toBeDefined();
      expect(screen.getAllByText("D1").length).toBeGreaterThan(0);
      expect(screen.getAllByText("D10").length).toBeGreaterThan(0);
    });
  });

  describe("DecileTable", () => {
    it("renders decile rows and small-sample warning", () => {
      render(
        <DecileTable
          deciles={[
            {
              decile: 1,
              score_min: 0,
              score_max: 20,
              sample_size: 15, // Below threshold 30
              mean_forward_return_pct: -1.5,
              median_forward_return_pct: -1.2,
              std_forward_return_pct: 3.4,
              annualized_return_pct: -15.0,
              positive_return_ratio: 0.38,
            },
            {
              decile: 10,
              score_min: 80,
              score_max: 100,
              sample_size: 45,
              mean_forward_return_pct: 3.8,
              median_forward_return_pct: 3.2,
              std_forward_return_pct: 4.1,
              annualized_return_pct: 42.0,
              positive_return_ratio: 0.65,
            },
          ]}
          minSamplesThreshold={30}
        />
      );
      expect(screen.getByText("Score Decile Statistical Breakdown")).toBeDefined();
      expect(screen.getByText("D1")).toBeDefined();
      expect(screen.getByText("D10")).toBeDefined();
      expect(screen.getByText("+3.80%")).toBeDefined();
      expect(screen.getByText("-1.50%")).toBeDefined();
      expect(screen.getByText("65.0%")).toBeDefined();
    });
  });

  describe("ModelGateAuditCard", () => {
    it("renders production gating audit controls", () => {
      render(<ModelGateAuditCard />);
      expect(screen.getByText("ML Model Production Gating Audit")).toBeDefined();
      expect(screen.getByText("Pre-Production Gate")).toBeDefined();
      expect(screen.getByText(/Audit Candidate Model A/i)).toBeDefined();
    });
  });

  describe("MemeDetailDrawer", () => {
    const mockMeme = {
      symbol: "BONK",
      name: "Bonk Dog",
      chain_id: "solana",
      dex_id: "raydium",
      pair_address: "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
      price_usd: 0.0000245,
      liquidity_usd: 1250000,
      volume_24h_usd: 8500000,
      volume_acceleration_1h: 2.4,
      volume_acceleration_5m: 1.8,
      buy_pressure_ratio: 0.62,
      pair_age_hours: 72,
      top_10_holders_pct: 35.5,
      holder_count: 65000,
      liquidity_score: 82,
      volume_momentum_score: 88,
      buy_pressure_score: 62,
      holder_distribution_score: 90,
      gross_score: 80.5,
      total_penalties: 0,
      opportunity_score: 80.5,
      risk_level: "LOW",
      risk_flags: [],
      penalties_breakdown: [],
    };

    it("renders meme details when open", () => {
      render(
        <MemeDetailDrawer
          meme={mockMeme}
          isOpen={true}
          onClose={() => {}}
        />
      );
      expect(screen.getByText("BONK")).toBeDefined();
      expect(screen.getByText("LOW RISK")).toBeDefined();
      expect(screen.getByText("Score Penalty Waterfall")).toBeDefined();
      expect(screen.getByText("Gross Score")).toBeDefined();
      expect(screen.getByText("DEX Microstructure Sub-Scores")).toBeDefined();
      expect(screen.getByText(/No active risk penalties triggered/i)).toBeDefined();
    });

    it("does not render when isOpen is false", () => {
      const { container } = render(
        <MemeDetailDrawer
          meme={mockMeme}
          isOpen={false}
          onClose={() => {}}
        />
      );
      expect(container.firstChild).toBeNull();
    });
  });

  describe("SectorRotationChart", () => {
    it("renders quadrants and sector points", () => {
      render(
        <SectorRotationChart
          sectors={[
            {
              sector_name: "DeFi",
              asset_count: 12,
              return_1d: 0.03,
              return_7d: 0.12,
              return_30d: 0.25,
              breadth_pct: 75,
              volume_change_7d_pct: 0.15,
              rotation_status: "LEADING",
            },
            {
              sector_name: "Layer 1",
              asset_count: 8,
              return_1d: -0.01,
              return_7d: -0.04,
              return_30d: 0.08,
              breadth_pct: 35,
              volume_change_7d_pct: -0.05,
              rotation_status: "DECLINING",
            },
          ]}
        />
      );
      expect(screen.getByText("Sector Rotation Quadrants (7D Return vs Breadth)")).toBeDefined();
      expect(screen.getByText("DeFi")).toBeDefined();
      expect(screen.getByText("Layer 1")).toBeDefined();
    });

    it("renders awaiting message when sectors are empty", () => {
      render(<SectorRotationChart sectors={[]} />);
      expect(screen.getByText(/Awaiting sector rotation telemetry/i)).toBeDefined();
    });
  });
});
