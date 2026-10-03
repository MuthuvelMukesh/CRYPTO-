import { describe, it, expect } from "vitest";
import {
  formatPrice,
  formatPercent,
  formatCompactUSD,
  formatScore,
  formatRelativeTime,
  EMPTY_FALLBACK,
} from "../src/lib/format";

describe("Financial Formatters & Invariant 2 (No Fake Data)", () => {
  describe("formatPrice", () => {
    it("returns em-dash on null or undefined", () => {
      expect(formatPrice(null)).toBe(EMPTY_FALLBACK);
      expect(formatPrice(undefined)).toBe(EMPTY_FALLBACK);
      expect(formatPrice("")).toBe(EMPTY_FALLBACK);
      expect(formatPrice(Number.NaN)).toBe(EMPTY_FALLBACK);
    });

    it("formats high-value crypto assets with 2 decimals", () => {
      expect(formatPrice(64120.5)).toBe("$64,120.50");
      expect(formatPrice("3450.1")).toBe("$3,450.10");
    });

    it("formats mid-range assets with 2 decimals", () => {
      expect(formatPrice(145.25)).toBe("$145.25");
      expect(formatPrice(1.05)).toBe("$1.05");
    });

    it("formats sub-dollar tokens with high precision", () => {
      expect(formatPrice(0.0004123)).toBe("$0.00041230");
      expect(formatPrice(0.00000543)).toBe("$0.00000543");
    });
  });

  describe("formatPercent", () => {
    it("returns em-dash on missing values", () => {
      expect(formatPercent(null)).toBe(EMPTY_FALLBACK);
      expect(formatPercent(undefined)).toBe(EMPTY_FALLBACK);
    });

    it("formats signed percentages correctly", () => {
      expect(formatPercent(5.24)).toBe("+5.24%");
      expect(formatPercent(-3.12)).toBe("-3.12%");
      expect(formatPercent(0)).toBe("0.00%");
    });

    it("converts fraction when isFraction is true", () => {
      expect(formatPercent(0.0524, { isFraction: true })).toBe("+5.24%");
      expect(formatPercent(-0.0312, { isFraction: true })).toBe("-3.12%");
    });
  });

  describe("formatCompactUSD", () => {
    it("returns em-dash on missing values", () => {
      expect(formatCompactUSD(null)).toBe(EMPTY_FALLBACK);
      expect(formatCompactUSD(undefined)).toBe(EMPTY_FALLBACK);
    });

    it("formats billions, millions, and thousands", () => {
      expect(formatCompactUSD(1500000000)).toBe("$1.50B");
      expect(formatCompactUSD(45200000)).toBe("$45.20M");
      expect(formatCompactUSD(12500)).toBe("$12.5K");
      expect(formatCompactUSD(450)).toBe("$450.00");
    });
  });

  describe("formatScore", () => {
    it("returns em-dash on null or undefined", () => {
      expect(formatScore(null)).toBe(EMPTY_FALLBACK);
    });

    it("formats scores to 1 decimal place", () => {
      expect(formatScore(84.26)).toBe("84.3");
      expect(formatScore(90)).toBe("90.0");
    });
  });

  describe("formatRelativeTime", () => {
    it("returns em-dash for null timestamp", () => {
      expect(formatRelativeTime(null)).toBe(EMPTY_FALLBACK);
    });

    it("returns human-readable elapsed time", () => {
      const now = new Date();
      expect(formatRelativeTime(now.toISOString())).toBe("just now");

      const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
      expect(formatRelativeTime(fiveMinutesAgo.toISOString())).toBe("5m ago");
    });
  });
});
