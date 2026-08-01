import { describe, expect, it } from "vitest";
import { isScoreValid, scoreRange } from "./review";

describe("scoreRange", () => {
  it("uses 0-100 for a tarea and 1-10 for an examen", () => {
    expect(scoreRange("tarea")).toEqual([0, 100]);
    expect(scoreRange("examen")).toEqual([1, 10]);
  });
});

describe("isScoreValid", () => {
  it("accepts the endpoints of each scale", () => {
    expect(isScoreValid(0, "tarea")).toBe(true);
    expect(isScoreValid(100, "tarea")).toBe(true);
    expect(isScoreValid(1, "examen")).toBe(true);
    expect(isScoreValid(10, "examen")).toBe(true);
  });

  it("rejects a tarea score above 100 and an examen score above 10", () => {
    expect(isScoreValid(101, "tarea")).toBe(false);
    expect(isScoreValid(85, "examen")).toBe(false);
  });

  it("rejects NaN and empty input", () => {
    expect(isScoreValid(Number.NaN, "tarea")).toBe(false);
  });
});
