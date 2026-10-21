import { describe, expect, it } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import { invalidateGrades } from "./grades";

describe("invalidateGrades", () => {
  it("marks the chip, the class panel sheet and every profile stale", () => {
    const qc = new QueryClient();
    const keys = [["grade"], ["student-grade", 1, 2], ["profile", "ana"], ["feed"]];
    for (const k of keys) qc.setQueryData(k, { x: 1 });
    invalidateGrades(qc);
    const stale = keys.map((k) => qc.getQueryState(k)?.isInvalidated);
    expect(stale).toEqual([true, true, true, false]);
  });
});
