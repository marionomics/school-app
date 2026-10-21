import { useEffect, useRef, useState } from "react";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { RiArrowUpLine } from "@remixicon/react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { mergePages, refreshFeed } from "@/lib/feed";
import PostCard from "@/components/PostCard";
import { FeedSkeleton } from "@/components/Skeletons";
import { es } from "@/strings/es";
import { useLikeMutation } from "@/lib/likes";
import { useAuth } from "@/lib/auth";
import { useVetoFlow } from "@/lib/useVetoFlow";
import type { FeedPage } from "@/lib/types";

export default function Home() {
  const q = useInfiniteQuery({
    queryKey: ["feed"],
    queryFn: ({ pageParam }) =>
      api<FeedPage>(`/api/feed?limit=20${pageParam ? `&cursor=${pageParam}` : ""}`),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    // Never refetch on its own: a refetch reorders under the reader's thumb.
    // refreshFeed() is the only way in (Bloque 4).
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  const like = useLikeMutation();
  const qc = useQueryClient();
  // Keyed on the load: a new as_of clears it without touching state.
  const [newFor, setNewFor] = useState<string | null>(null);
  const asOf = q.data?.pages[0]?.as_of;
  const hasNew = asOf != null && newFor === asOf;

  // Coming back never reorders (Mario, 2026-10-21): ask whether something
  // new exists and offer it instead.
  useEffect(() => {
    if (!asOf) return;
    const check = () => {
      if (document.visibilityState !== "visible") return;
      api<{ has_new: boolean }>(`/api/feed/has-new?since=${encodeURIComponent(asOf)}`)
        .then((r) => r.has_new && setNewFor(asOf))
        .catch(() => {});
    };
    check();
    document.addEventListener("visibilitychange", check);
    return () => document.removeEventListener("visibilitychange", check);
  }, [asOf]);

  function showNew() {
    setNewFor(null);
    window.scrollTo({ top: 0 });
    void refreshFeed(qc);
  }
  const { user } = useAuth();
  const veto = useVetoFlow();
  const onVeto = user?.role === "teacher" ? veto.request : undefined;
  const sentinel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = sentinel.current;
    if (!el) return;
    const obs = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && q.hasNextPage && !q.isFetchingNextPage) {
        void q.fetchNextPage();
      }
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, [q]);

  if (q.isPending) return <FeedSkeleton />;
  if (q.isError)
    return <p className="p-6 text-center text-muted-foreground">{es.feed.error}</p>;

  const posts = mergePages(q.data.pages);
  // Every page carries the same pinned list; merging them would repeat it.
  const pinned = q.data.pages[0]?.pinned ?? [];
  const pinnedIds = new Set(pinned.map((p) => p.id));

  return (
    <div className="divide-y">
      {hasNew && (
        <div className="pointer-events-none sticky top-14 z-10 flex justify-center py-2">
          <Button size="sm" className="pointer-events-auto shadow-md" onClick={showNew}>
            <RiArrowUpLine data-icon="inline-start" />
            {es.feed.newPosts}
          </Button>
        </div>
      )}
      {veto.dialog}
      {pinned.length > 0 && (
        <section className="border-b bg-muted/40">
          <p className="px-4 pt-3 text-[10px] font-semibold tracking-widest uppercase text-muted-foreground">
            {es.feed.pinnedHeader}
          </p>
          <div className="divide-y">
            {pinned.map((p) => (
              <PostCard
                key={`pinned-${p.id}`}
                post={p}
                onLike={(post) => like.mutate(post)}
                onVeto={onVeto}
              />
            ))}
          </div>
        </section>
      )}
      {posts.length === 0 && (
        <p className="p-10 text-center text-muted-foreground">{es.feed.empty}</p>
      )}
      {posts.filter((p) => !pinnedIds.has(p.id)).map((p) => (
        <PostCard
          key={p.id}
          post={p}
          onLike={(post) => like.mutate(post)}
          onVeto={onVeto}
        />
      ))}
      <div ref={sentinel} />
      {!q.hasNextPage && posts.length > 0 && (
        <p className="p-6 text-center text-sm text-muted-foreground">{es.feed.end}</p>
      )}
    </div>
  );
}
