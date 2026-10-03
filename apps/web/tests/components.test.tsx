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
});
