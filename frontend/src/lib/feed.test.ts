import { describe, expect, it } from "vitest";
import { mergePages } from "./feed";
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
    attachments: [],
    created_at: "2026-07-22T00:00:00Z",
    last_activity_at: "2026-07-22T00:00:00Z",
    parent_id: null,
    due_date: null,
    is_entrega: false,
  }) as Post;

describe("mergePages", () => {
  it("flattens and dedups by id keeping first occurrence", () => {
    const pages: FeedPage[] = [
      { items: [post(3), post(2)], next_cursor: "c1" },
      { items: [post(2), post(1)], next_cursor: null }, // 2 re-appeared after a bump
    ];
    const merged = mergePages(pages);
    expect(merged.map((p) => p.id)).toEqual([3, 2, 1]);
  });

  it("handles empty pages", () => {
    expect(mergePages([])).toEqual([]);
    expect(mergePages([{ items: [], next_cursor: null }])).toEqual([]);
  });
});
