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
