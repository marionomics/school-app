import { useEffect, useRef } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { mergePages } from "@/lib/feed";
import PostCard from "@/components/PostCard";
import { FeedSkeleton } from "@/components/Skeletons";
import { es } from "@/strings/es";
import { useLikeMutation } from "@/lib/likes";
import type { FeedPage } from "@/lib/types";

export default function Home() {
  const q = useInfiniteQuery({
    queryKey: ["feed"],
    queryFn: ({ pageParam }) =>
      api<FeedPage>(`/api/feed?limit=20${pageParam ? `&cursor=${pageParam}` : ""}`),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const like = useLikeMutation();
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

  return (
    <div className="divide-y">
      {pinned.length > 0 && (
        <section className="border-b bg-muted/40">
          <p className="px-4 pt-3 text-[10px] font-semibold tracking-widest uppercase text-muted-foreground">
            {es.feed.pinnedHeader}
          </p>
          <div className="divide-y">
            {pinned.map((p) => (
              // The same post can also appear below in `items`; the key prefix
              // keeps the two instances distinct for React.
              <PostCard
                key={`pinned-${p.id}`}
                post={p}
                onLike={(post) => like.mutate(post)}
              />
            ))}
          </div>
        </section>
      )}
      {posts.length === 0 && (
        <p className="p-10 text-center text-muted-foreground">{es.feed.empty}</p>
      )}
      {posts.map((p) => (
        <PostCard key={p.id} post={p} onLike={(post) => like.mutate(post)} />
      ))}
      <div ref={sentinel} />
      {!q.hasNextPage && posts.length > 0 && (
        <p className="p-6 text-center text-sm text-muted-foreground">{es.feed.end}</p>
      )}
    </div>
  );
}
