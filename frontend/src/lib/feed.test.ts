import { describe, expect, it } from "vitest";
import { QueryClient, type InfiniteData } from "@tanstack/react-query";
import { firstPageOnly, mergePages, refreshFeed } from "./feed";
import type { FeedPage, Post } from "./types";

const post = (id: number): Post =>
  ({
    id,
    author: { id: 1, username: "u", name: "U", avatar_url: null, role: "student" },
    type: "regular",
    class_id: null,
    class_name: null,
    content: `p${id}`,
    taps: null,
    status: "active",
    like_count: 0,
    reply_count: 0,
    liked_by_me: false,
    teacher_aura: false,
    attachments: [],
    created_at: "2026-07-22T00:00:00Z",
    last_activity_at: "2026-07-22T00:00:00Z",
    parent_id: null,
    due_date: null,
    is_entrega: false,
    examen_mode: null,
    graded_at: null,
    my_review: null,
    veto_reason: null,
  }) as Post;

describe("mergePages", () => {
  it("flattens and dedups by id keeping first occurrence", () => {
    const pages: FeedPage[] = [
      { items: [post(3), post(2)], pinned: [], next_cursor: "c1" },
      { items: [post(2), post(1)], pinned: [], next_cursor: null }, // 2 re-appeared after a bump
    ];
    const merged = mergePages(pages);
    expect(merged.map((p) => p.id)).toEqual([3, 2, 1]);
  });

  it("handles empty pages", () => {
    expect(mergePages([])).toEqual([]);
    expect(mergePages([{ items: [], pinned: [], next_cursor: null }])).toEqual([]);
  });
});

const page = (ids: number[], cursor: string | null): FeedPage => ({
  items: ids.map(post),
  pinned: [],
  next_cursor: cursor,
  as_of: "2026-10-21T12:00:00+00:00",
});

describe("firstPageOnly", () => {
  it("keeps only page 1 so a refetch never mixes a new as_of with old cursors", () => {
    const d: InfiniteData<FeedPage> = {
      pages: [page([1, 2], "c1"), page([3], null)],
      pageParams: [null, "c1"],
    };
    const out = firstPageOnly(d)!;
    expect(out.pages).toHaveLength(1);
    expect(out.pageParams).toEqual([null]);
  });

  it("leaves an empty cache alone", () => {
    expect(firstPageOnly(undefined)).toBeUndefined();
  });
});

describe("refreshFeed", () => {
  it("truncates and marks the feed stale", async () => {
    const qc = new QueryClient();
    qc.setQueryData(["feed"], {
      pages: [page([1], "c1"), page([2], null)],
      pageParams: [null, "c1"],
    });
    await refreshFeed(qc);
    const d = qc.getQueryData<InfiniteData<FeedPage>>(["feed"])!;
    expect(d.pages).toHaveLength(1);
    expect(qc.getQueryState(["feed"])!.isInvalidated).toBe(true);
  });
});
