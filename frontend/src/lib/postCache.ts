import type { InfiniteData, QueryClient } from "@tanstack/react-query";
import type { FeedPage, Post, ThreadResponse } from "./types";

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

/** Applies fn to this post wherever it is cached and returns the rollback. */
export async function patchPostInCaches(
  qc: QueryClient,
  post: Post,
  fn: (p: Post) => Post,
): Promise<() => void> {
  const feedKey = ["feed"];
  const threadKey = ["thread", String(post.parent_id ?? post.id)];
  await qc.cancelQueries({ queryKey: feedKey });
  const prevFeed = qc.getQueryData<InfiniteData<FeedPage>>(feedKey);
  const prevThread = qc.getQueryData<ThreadResponse>(threadKey);
  qc.setQueryData<InfiniteData<FeedPage>>(feedKey, (d) => mapFeed(d, post.id, fn));
  qc.setQueryData<ThreadResponse>(threadKey, (t) => mapThread(t, post.id, fn));
  return () => {
    if (prevFeed) qc.setQueryData(feedKey, prevFeed);
    if (prevThread) qc.setQueryData(threadKey, prevThread);
  };
}
