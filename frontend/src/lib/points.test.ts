import { describe, expect, it } from "vitest";
import { formatPoints, likeCurvePreview } from "./points";

describe("formatPoints", () => {
  it("states one point as one décima", () => {
    expect(formatPoints(1)).toBe("1 punto · 1 décima");
  });

  it("spells out a half point on the 10-scale", () => {
    expect(formatPoints(5)).toBe("5 puntos · 5 décimas · medio punto de 10");
  });

  it("describes a falta as a whole point on the 10-scale", () => {
    expect(formatPoints(-10)).toBe("10 puntos · 10 décimas · un punto entero de 10");
  });

  it("reads a magnitude, not a sign — the minus belongs to the caller's label", () => {
    expect(formatPoints(-10)).toBe(formatPoints(10));
  });

  it("adds the 10-scale clause only when it lands on a whole point", () => {
    expect(formatPoints(3)).toBe("3 puntos · 3 décimas");
    expect(formatPoints(20)).toBe("20 puntos · 20 décimas · 2 puntos enteros de 10");
  });

  it("handles a fractional value", () => {
    expect(formatPoints(0.5)).toBe("0.5 puntos · media décima");
  });

  it("handles zero", () => {
    expect(formatPoints(0)).toBe("0 puntos");
  });
});

describe("likeCurvePreview", () => {
  it("matches the engine's concave curve at the three offered exponents", () => {
    expect(likeCurvePreview(0.5)).toBe(10); // sqrt(100)
    expect(likeCurvePreview(0.75)).toBe(32); // 100^0.75 = 31.6
    expect(likeCurvePreview(1.0)).toBe(100);
  });

  it("accepts a different like count", () => {
    expect(likeCurvePreview(0.5, 25)).toBe(5);
  });
});
