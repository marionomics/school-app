import { describe, expect, it } from "vitest";
import type { InfiniteData } from "@tanstack/react-query";
import { mapFeed, mapThread, toggleAura } from "./postCache";
import type { FeedPage, Post } from "./types";

const post = (id: number, over: Partial<Post> = {}): Post =>
  ({
    id,
    author: { id: 1, username: "u", name: "U", avatar_url: null, role: "student" },
    type: "participacion",
    class_id: 1,
    class_name: "Micro",
    content: `p${id}`,
    taps: 1,
    status: "active",
    like_count: 0,
    reply_count: 0,
    liked_by_me: false,
    teacher_aura: false,
    attachments: [],
    created_at: "2026-10-17T00:00:00Z",
    last_activity_at: "2026-10-17T00:00:00Z",
    parent_id: null,
    due_date: null,
    is_entrega: false,
    examen_mode: null,
    graded_at: null,
    my_review: null,
    veto_reason: null,
    ...over,
  }) as Post;

describe("toggleAura", () => {
  it("a student's aura changes the count, never the teacher mark", () => {
    const on = toggleAura(post(1), false);
    expect(on).toMatchObject({ liked_by_me: true, like_count: 1, teacher_aura: false });
    const off = toggleAura(post(1, { liked_by_me: true, like_count: 1, teacher_aura: true }), false);
    expect(off).toMatchObject({ liked_by_me: false, like_count: 0, teacher_aura: true });
  });

  it("the teacher's aura turns the teacher mark on and off with it", () => {
    expect(toggleAura(post(1), true).teacher_aura).toBe(true);
    const off = toggleAura(post(1, { liked_by_me: true, like_count: 1, teacher_aura: true }), true);
    expect(off.teacher_aura).toBe(false);
  });

  it("never goes below zero", () => {
    expect(toggleAura(post(1, { liked_by_me: true, like_count: 0 }), false).like_count).toBe(0);
  });
});

describe("mapFeed", () => {
  const feed: InfiniteData<FeedPage> = {
    pageParams: [null],
    pages: [{ items: [post(1), post(2)], pinned: [post(3, { type: "tarea" })], next_cursor: null }],
  };

  it("patches pinned as well as items", () => {
    const out = mapFeed(feed, 3, (p) => toggleAura(p, true))!;
    expect(out.pages[0].pinned[0].liked_by_me).toBe(true);
    expect(mapFeed(feed, 2, (p) => toggleAura(p, true))!.pages[0].items[1].liked_by_me).toBe(true);
  });

  it("does not mutate the snapshot it was given, so rollback restores it", () => {
    mapFeed(feed, 1, (p) => toggleAura(p, true));
    expect(feed.pages[0].items[0].liked_by_me).toBe(false);
  });

  it("passes undefined through", () => {
    expect(mapFeed(undefined, 1, (p) => p)).toBeUndefined();
  });
});

describe("mapThread", () => {
  it("patches the root or a reply", () => {
    const t = { post: post(1), replies: [post(2, { parent_id: 1 })] };
    expect(mapThread(t, 1, (p) => ({ ...p, status: "vetoed" }))!.post.status).toBe("vetoed");
    expect(mapThread(t, 2, (p) => ({ ...p, status: "vetoed" }))!.replies[0].status).toBe("vetoed");
  });
});
