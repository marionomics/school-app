import { describe, expect, it } from "vitest";
import { initialTapState, tapReducer, TAP_WINDOW_MS } from "./tapWindow";

describe("tapReducer", () => {
  it("first tap starts the window", () => {
    const s = tapReducer(initialTapState, { type: "tap", now: 1000 });
    expect(s.count).toBe(1);
    expect(s.deadline).toBe(1000 + TAP_WINDOW_MS);
  });

  it("extra taps escalate to 3 and reset the window", () => {
    let s = tapReducer(initialTapState, { type: "tap", now: 0 });
    s = tapReducer(s, { type: "tap", now: 500 });
    s = tapReducer(s, { type: "tap", now: 900 });
    expect(s.count).toBe(3);
    expect(s.deadline).toBe(900 + TAP_WINDOW_MS);
    const s4 = tapReducer(s, { type: "tap", now: 1200 });
    expect(s4.count).toBe(3); // capped
    expect(s4.deadline).toBe(1200 + TAP_WINDOW_MS); // but window resets
  });

  it("expire publishes only after deadline", () => {
    let s = tapReducer(initialTapState, { type: "tap", now: 0 });
    s = tapReducer(s, { type: "expire", now: 100 });
    expect(s.published).toBe(false);
    s = tapReducer(s, { type: "expire", now: TAP_WINDOW_MS + 1 });
    expect(s.published).toBe(true);
  });

  it("cancel resets everything", () => {
    let s = tapReducer(initialTapState, { type: "tap", now: 0 });
    s = tapReducer(s, { type: "cancel" });
    expect(s).toEqual(initialTapState);
  });

  it("taps after publish are ignored", () => {
    let s = tapReducer(initialTapState, { type: "tap", now: 0 });
    s = tapReducer(s, { type: "expire", now: TAP_WINDOW_MS + 1 });
    const after = tapReducer(s, { type: "tap", now: 5000 });
    expect(after).toEqual(s);
  });
});
