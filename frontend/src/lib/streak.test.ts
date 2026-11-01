import { describe, expect, it } from "vitest";
import { daysToNext, levelsSummary, multiplierToast, pct } from "./streak";
import type { StreakMe } from "./types";

const base: StreakMe = {
  days: 5, today_done: true, level: null, next_level_at: 7,
  odds: { x2: 0.15, x3: 0 }, levels: [],
};

describe("streak helpers", () => {
  it("counts the days to the next level", () => {
    expect(daysToNext(base)).toBe(2);
    expect(daysToNext({ ...base, next_level_at: null })).toBeNull();
  });
  it("toasts only on 2× and 3×", () => {
    expect(multiplierToast(3)).toBe("¡Tu publicación salió triple!");
    expect(multiplierToast(2)).toBe("¡Tu publicación salió doble!");
    expect(multiplierToast(null)).toBeNull();
    expect(multiplierToast(1)).toBeNull();
  });
  it("formats odds and the level summary", () => {
    expect(pct(0.15)).toBe("15%");
    expect(pct(0.05)).toBe("5%");
    expect(levelsSummary([
      { from_days: 3, x2: 0.15, x3: 0 },
      { from_days: 7, x2: 0.2, x3: 0.05 },
    ])).toBe("3/7");
  });
});
