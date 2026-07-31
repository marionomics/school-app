import { describe, expect, it } from "vitest";
import { latenessTier } from "./lateness";

const DUE = new Date("2026-08-09T23:59:00Z");
const at = (ms: number) => new Date(DUE.getTime() + ms);
const HOUR = 3600_000;
const DAY = 24 * HOUR;

describe("latenessTier", () => {
  it("on time before and exactly at the deadline", () => {
    expect(latenessTier(at(-DAY), DUE).pct).toBe(100);
    expect(latenessTier(at(0), DUE).pct).toBe(100);
  });

  it("under 24h is 90", () => {
    expect(latenessTier(at(HOUR), DUE).pct).toBe(90);
    expect(latenessTier(at(23 * HOUR), DUE).pct).toBe(90);
  });

  it("exactly 24h is already 50", () => {
    expect(latenessTier(at(24 * HOUR), DUE).pct).toBe(50);
  });

  it("exactly 7 days is already 20", () => {
    expect(latenessTier(at(7 * DAY), DUE).pct).toBe(20);
    expect(latenessTier(at(30 * DAY), DUE).pct).toBe(20);
  });
});
