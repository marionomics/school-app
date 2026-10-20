import { describe, expect, it } from "vitest";
import { MAX_CANVAS_PIXELS, capPixels, centerSquare, fitWithin, isHeic, shouldShrink } from "./images";

const f = (type: string, name = "x") => ({ type, name });

describe("fitWithin", () => {
  it("never enlarges", () => {
    expect(fitWithin(800, 600, 2048)).toEqual({ width: 800, height: 600 });
  });
  it("shrinks the long side to max, keeping proportions (landscape and portrait)", () => {
    expect(fitWithin(4032, 3024, 2048)).toEqual({ width: 2048, height: 1536 });
    expect(fitWithin(3024, 4032, 2048)).toEqual({ width: 1536, height: 2048 });
  });
  it("rounds to whole pixels", () => {
    const { width, height } = fitWithin(4000, 3001, 2048);
    expect(Number.isInteger(width) && Number.isInteger(height)).toBe(true);
  });
});

describe("centerSquare", () => {
  it("crops the centre of a landscape and a portrait photo", () => {
    expect(centerSquare(4000, 3000)).toEqual({ sx: 500, sy: 0, size: 3000 });
    expect(centerSquare(3000, 4000)).toEqual({ sx: 0, sy: 500, size: 3000 });
  });
});

describe("shouldShrink", () => {
  it("re-encodes the photo formats", () => {
    for (const t of ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"])
      expect(shouldShrink(f(t))).toBe(true);
  });
  it("never touches GIF, SVG or non-images", () => {
    for (const t of ["image/gif", "image/svg+xml", "application/pdf", "text/plain"])
      expect(shouldShrink(f(t))).toBe(false);
  });
  it("recognises a HEIC with no type by its extension", () => {
    expect(shouldShrink(f("", "IMG_0001.HEIC"))).toBe(true);
    expect(isHeic(f("", "IMG_0001.heif"))).toBe(true);
    expect(shouldShrink(f("", "notes.txt"))).toBe(false);
  });
});

describe("capPixels", () => {
  it("leaves a canvas under the limit alone", () => {
    expect(capPixels(2048, 1536, MAX_CANVAS_PIXELS)).toEqual({ width: 2048, height: 1536 });
  });
  it("scales an oversized canvas under the limit, keeping proportions", () => {
    const { width, height } = capPixels(8000, 6000, MAX_CANVAS_PIXELS);
    expect(width * height).toBeLessThanOrEqual(MAX_CANVAS_PIXELS);
    expect(Math.abs(width / height - 8000 / 6000)).toBeLessThan(0.01);
  });
  it("uses the iOS limit of 16 777 216 px", () => {
    expect(MAX_CANVAS_PIXELS).toBe(16_777_216);
  });
});
