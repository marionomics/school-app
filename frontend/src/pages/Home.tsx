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
  return (
    <div className="divide-y">
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
