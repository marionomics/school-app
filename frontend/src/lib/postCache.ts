import type { InfiniteData, QueryClient } from "@tanstack/react-query";
import type { FeedPage, Post, ProfilePostsPage, ThreadResponse } from "./types";

/** Optimistic aura. A teacher's tap also flips the visible "profe" mark;
 *  a student's never does. */
export function toggleAura(p: Post, viewerIsTeacher: boolean): Post {
  const on = !p.liked_by_me;
  return {
    ...p,
    liked_by_me: on,
    like_count: Math.max(0, p.like_count + (on ? 1 : -1)),
    teacher_aura: viewerIsTeacher ? on : p.teacher_aura,
  };
}

/** Validating is the teacher's aura (Bloque 2): set it on or off, idempotently. */
export function teacherAura(p: Post, on: boolean): Post {
  if (p.liked_by_me === on) return { ...p, teacher_aura: on };
  return {
    ...p,
    liked_by_me: on,
    teacher_aura: on,
    like_count: Math.max(0, p.like_count + (on ? 1 : -1)),
  };
}

const patch = (id: number, fn: (p: Post) => Post) => (p: Post) =>
  p.id === id ? fn(p) : p;

/** Pinned too: a tarea under "Por entregar" is the same post. */
export function mapFeed(
  data: InfiniteData<FeedPage> | undefined,
  id: number,
  fn: (p: Post) => Post,
): InfiniteData<FeedPage> | undefined {
  if (!data) return data;
  return {
    ...data,
    pages: data.pages.map((pg) => ({
      ...pg,
      items: pg.items.map(patch(id, fn)),
      pinned: pg.pinned.map(patch(id, fn)),
    })),
  };
}

export function mapThread(
  t: ThreadResponse | undefined,
  id: number,
  fn: (p: Post) => Post,
): ThreadResponse | undefined {
  if (!t) return t;
  return { post: patch(id, fn)(t.post), replies: t.replies.map(patch(id, fn)) };
}

/** A profile tab: same post, plus the `parent` excerpt a reply carries,
 *  which the spread keeps. */
export function mapProfilePosts(
  data: InfiniteData<ProfilePostsPage> | undefined,
  id: number,
  fn: (p: Post) => Post,
): InfiniteData<ProfilePostsPage> | undefined {
  if (!data) return data;
  return {
    ...data,
    pages: data.pages.map((pg) => ({
      ...pg,
      items: pg.items.map((p) => (p.id === id ? { ...p, ...fn(p) } : p)),
    })),
  };
}

/** Applies fn to this post wherever it is cached and returns the rollback.
 *  The rollback applies undo to this one post in the caches as they are
 *  then, never a snapshot: restoring a snapshot would also wipe any other
 *  optimistic patch that landed meanwhile on another post. */
export async function patchPostInCaches(
  qc: QueryClient,
  post: Post,
  fn: (p: Post) => Post,
  undo: (p: Post) => Post,
): Promise<() => void> {
  const feedKey = ["feed"];
  const threadKey = ["thread", String(post.parent_id ?? post.id)];
  // Every cached profile tab, whoever's profile it is: the key says whose
  // tab it is, not which posts are in it.
  const profileKey = ["profile-posts"];
  await qc.cancelQueries({ queryKey: feedKey });
  await qc.cancelQueries({ queryKey: profileKey });
  const apply = (f: (p: Post) => Post) => {
    qc.setQueryData<InfiniteData<FeedPage>>(feedKey, (d) => mapFeed(d, post.id, f));
    qc.setQueriesData<InfiniteData<ProfilePostsPage>>({ queryKey: profileKey }, (d) =>
      mapProfilePosts(d, post.id, f),
    );
    qc.setQueryData<ThreadResponse>(threadKey, (t) => mapThread(t, post.id, f));
  };
  apply(fn);
  return () => apply(undo);
}

/** For screens that know a post's id but not the Post (the review queue,
 *  a thread's root). Patches; never refetches — a refetch reorders. */
export function patchFeedPost(qc: QueryClient, id: number, fn: (p: Post) => Post): void {
  qc.setQueryData<InfiniteData<FeedPage>>(["feed"], (d) => mapFeed(d, id, fn));
}

/** A deleted root leaves the feed (the server hides it too). */
export function dropFromFeed(qc: QueryClient, id: number): void {
  qc.setQueryData<InfiniteData<FeedPage>>(["feed"], (d) =>
    d && {
      ...d,
      pages: d.pages.map((pg) => ({
        ...pg,
        items: pg.items.filter((p) => p.id !== id),
        pinned: pg.pinned.filter((p) => p.id !== id),
      })),
    },
  );
}
