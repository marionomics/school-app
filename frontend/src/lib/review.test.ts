import { describe, expect, it } from "vitest";
import {
  acceptSuggested,
  bulkReviewed,
  isScoreValid,
  scoreRange,
  ungradedEntregaIds,
} from "./review";
import type { Post } from "./types";

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

describe("bulkReviewed", () => {
  it("sends exactly the ids given, in order", async () => {
    const calls: { url: string; body: unknown }[] = [];
    const original = globalThis.fetch;
    // The test env is node, so api()'s token lookup has nothing to read from.
    globalThis.localStorage = {
      getItem: () => null,
    } as unknown as Storage;
    globalThis.fetch = (async (url: string, init: RequestInit) => {
      calls.push({ url, body: JSON.parse(init.body as string) });
      return new Response(JSON.stringify({ reviewed: 2 }), { status: 200 });
    }) as unknown as typeof fetch;

    await bulkReviewed([7, 3]);
    globalThis.fetch = original;

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe("/api/review/participaciones/reviewed");
    expect(calls[0].body).toEqual({ post_ids: [7, 3] });
  });
});

describe("acceptSuggested", () => {
  it("sends the tarea and exactly the entregas on screen", async () => {
    const calls: { url: string; body: unknown }[] = [];
    const original = globalThis.fetch;
    globalThis.localStorage = { getItem: () => null } as unknown as Storage;
    globalThis.fetch = (async (url: string, init: RequestInit) => {
      calls.push({ url, body: JSON.parse(init.body as string) });
      return new Response(JSON.stringify({ graded: 2 }), { status: 200 });
    }) as unknown as typeof fetch;

    await acceptSuggested(5, [9, 4]);
    globalThis.fetch = original;

    expect(calls[0].url).toBe("/api/reviews/accept-suggested");
    expect(calls[0].body).toEqual({ item_post_id: 5, entrega_post_ids: [9, 4] });
  });
});

describe("ungradedEntregaIds", () => {
  const reply = (id: number, over: Partial<Post>): Post =>
    ({ id, is_entrega: false, my_review: null, status: "active", ...over }) as Post;

  it("keeps entregas without a review, nothing else", () => {
    const replies = [
      reply(1, { is_entrega: true }),
      reply(2, { is_entrega: true, my_review: { score: 80 } as Post["my_review"] }),
      reply(3, {}),
      reply(4, { is_entrega: true, status: "deleted" }),
    ];
    expect(ungradedEntregaIds(replies)).toEqual([1]);
  });
});
