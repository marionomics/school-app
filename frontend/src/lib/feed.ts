import type { InfiniteData, QueryClient } from "@tanstack/react-query";
import type { FeedPage, Post } from "./types";

export function mergePages(pages: FeedPage[]): Post[] {
  const seen = new Set<number>();
  const out: Post[] = [];
  for (const page of pages) {
    for (const p of page.items) {
      if (!seen.has(p.id)) {
        seen.add(p.id);
        out.push(p);
      }
    }
  }
  return out;
}

/** Page 1 only. Refetching every stored page would pair a fresh first page
 *  (new as_of) with cursors frozen at the old one. */
export function firstPageOnly(
  d: InfiniteData<FeedPage> | undefined,
): InfiniteData<FeedPage> | undefined {
  if (!d) return d;
  return { pages: d.pages.slice(0, 1), pageParams: d.pageParams.slice(0, 1) };
}

/** The only way the feed reorders (Bloque 4): publishing, tapping Inicio
 *  on Inicio, and the new-posts pill. Everything else patches the cache. */
export function refreshFeed(qc: QueryClient): Promise<void> {
  qc.setQueryData<InfiniteData<FeedPage>>(["feed"], firstPageOnly);
  return qc.invalidateQueries({ queryKey: ["feed"], exact: true });
}
