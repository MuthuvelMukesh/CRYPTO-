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
});
