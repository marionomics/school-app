import { describe, expect, it } from "vitest";
import { QueryClient, type InfiniteData } from "@tanstack/react-query";
import {
  dropFromFeed,
  mapFeed,
  mapThread,
  patchFeedPost,
  patchPostInCaches,
  teacherAura,
  toggleAura,
} from "./postCache";
import type { FeedPage, Post, ProfilePostsPage } from "./types";

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
    pages: [{ items: [post(1), post(2)], pinned: [post(3, { type: "tarea" })], next_cursor: null, as_of: "x" }],
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

describe("patchPostInCaches", () => {
  const seed = () => {
    const qc = new QueryClient();
    const reply = post(2, { parent_id: 1 });
    qc.setQueryData<InfiniteData<FeedPage>>(["feed"], {
      pageParams: [null],
      pages: [{ items: [post(1), reply], pinned: [post(3, { type: "tarea" })], next_cursor: null, as_of: "x" }],
    });
    qc.setQueryData(["thread", "1"], { post: post(1), replies: [reply] });
    qc.setQueryData(["thread", "3"], { post: post(3, { type: "tarea" }), replies: [] });
    return { qc, reply };
  };
  const feedOf = (qc: QueryClient) => qc.getQueryData<InfiniteData<FeedPage>>(["feed"])!.pages[0];
  const aura = (p: Post) => toggleAura(p, true);

  it("patches the post in feed items, feed pinned and its thread", async () => {
    const { qc, reply } = seed();
    await patchPostInCaches(qc, reply, aura, aura);
    expect(feedOf(qc).items[1].liked_by_me).toBe(true);
    expect(qc.getQueryData<{ replies: Post[] }>(["thread", "1"])!.replies[0].liked_by_me).toBe(true);

    await patchPostInCaches(qc, post(3, { type: "tarea" }), aura, aura);
    expect(feedOf(qc).pinned[0].liked_by_me).toBe(true);
    expect(qc.getQueryData<{ post: Post }>(["thread", "3"])!.post.liked_by_me).toBe(true);
  });

  it("rolling back one post leaves a later patch on another post in place", async () => {
    const { qc, reply } = seed();
    const rollback1 = await patchPostInCaches(qc, post(1), aura, aura);
    const veto = (p: Post) => ({ ...p, status: "vetoed" as const });
    await patchPostInCaches(qc, reply, veto, (p) => ({ ...p, status: "active" }));
    rollback1();
    expect(feedOf(qc).items[0].liked_by_me).toBe(false);
    expect(feedOf(qc).items[1].status).toBe("vetoed");
    const t = qc.getQueryData<{ post: Post; replies: Post[] }>(["thread", "1"])!;
    expect(t.post.liked_by_me).toBe(false);
    expect(t.replies[0].status).toBe("vetoed");
  });

  it("patches a profile tab too, and keeps the reply's parent excerpt", async () => {
    const { qc, reply } = seed();
    const parent = { id: 1, author_username: "u", excerpt: "p1" };
    qc.setQueryData<InfiniteData<ProfilePostsPage>>(["profile-posts", "u", "replies"], {
      pageParams: [null],
      pages: [{ items: [{ ...reply, parent }], next_cursor: null }],
    });
    const rollback = await patchPostInCaches(qc, reply, aura, aura);
    const tab = () =>
      qc.getQueryData<InfiniteData<ProfilePostsPage>>(["profile-posts", "u", "replies"])!
        .pages[0].items[0];
    expect(tab().liked_by_me).toBe(true);
    expect(tab().parent).toEqual(parent);
    rollback();
    expect(tab().liked_by_me).toBe(false);
  });
});

function seeded() {
  const qc = new QueryClient();
  qc.setQueryData(["feed"], {
    pages: [{ items: [post(1), post(2)], pinned: [post(2)], next_cursor: null, as_of: "x" }],
    pageParams: [null],
  });
  return qc;
}

describe("patchFeedPost", () => {
  it("patches the post in items and pinned without refetching", () => {
    const qc = seeded();
    patchFeedPost(qc, 2, (p) => ({ ...p, reply_count: p.reply_count + 1 }));
    const d = qc.getQueryData<InfiniteData<FeedPage>>(["feed"])!;
    expect(d.pages[0].items[1].reply_count).toBe(1);
    expect(d.pages[0].pinned[0].reply_count).toBe(1);
    expect(qc.getQueryState(["feed"])!.isInvalidated).toBe(false);
  });
});

describe("dropFromFeed", () => {
  it("removes a deleted root from items and pinned", () => {
    const qc = seeded();
    dropFromFeed(qc, 2);
    const d = qc.getQueryData<InfiniteData<FeedPage>>(["feed"])!;
    expect(d.pages[0].items.map((p) => p.id)).toEqual([1]);
    expect(d.pages[0].pinned).toEqual([]);
  });
});

describe("teacherAura", () => {
  it("validating turns the teacher's aura on once", () => {
    const on = teacherAura(post(1), true);
    expect(on).toMatchObject({ liked_by_me: true, teacher_aura: true, like_count: 1 });
    expect(teacherAura(on, true).like_count).toBe(1);
  });

  it("un-validating turns it off", () => {
    const off = teacherAura(teacherAura(post(1), true), false);
    expect(off).toMatchObject({ liked_by_me: false, teacher_aura: false, like_count: 0 });
  });
});
