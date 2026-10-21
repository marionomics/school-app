import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { RiSparkling2Line } from "@remixicon/react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLikeMutation } from "@/lib/likes";
import { useVetoFlow } from "@/lib/useVetoFlow";
import { formatPoints } from "@/lib/points";
import Avatar from "@/components/Avatar";
import PostCard from "@/components/PostCard";
import GradeBreakdown from "@/components/GradeBreakdown";
import ProfileEditor from "@/components/ProfileEditor";
import RemovePhotoButton from "@/components/RemovePhotoButton";
import { FeedSkeleton } from "@/components/Skeletons";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { es } from "@/strings/es";
import type { ProfileHeader, ProfilePostsPage } from "@/lib/types";

type Tab = "posts" | "replies";

function PostList({ username, tab }: { username: string; tab: Tab }) {
  const { user } = useAuth();
  const like = useLikeMutation();
  const veto = useVetoFlow();
  const sentinel = useRef<HTMLDivElement>(null);
  const q = useInfiniteQuery({
    queryKey: ["profile-posts", username, tab],
    queryFn: ({ pageParam }) =>
      api<ProfilePostsPage>(
        `/api/users/${encodeURIComponent(username)}/posts?tab=${tab}&limit=20${
          pageParam ? `&cursor=${pageParam}` : ""}`,
      ),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });

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
  if (q.isError) return <p className="p-6 text-center text-muted-foreground">{es.feed.error}</p>;
  const items = q.data.pages.flatMap((p) => p.items);
  if (items.length === 0 && !q.hasNextPage)
    return (
      <p className="p-6 text-center text-sm text-muted-foreground">
        {tab === "posts" ? es.profile.emptyPosts : es.profile.emptyReplies}
      </p>
    );
  return (
    <div className="divide-y">
      {veto.dialog}
      {items.map((p) => (
        <div key={p.id}>
          {p.parent && (
            <Link to={`/post/${p.parent.id}`}
                  className="block px-4 pt-3 text-xs text-muted-foreground">
              {es.profile.replyingTo.replace("{user}", p.parent.author_username ?? "")}{" "}
              <span className="line-clamp-1">{p.parent.excerpt}</span>
            </Link>
          )}
          <PostCard post={p} onLike={(x) => like.mutate(x)}
                    onVeto={user?.role === "teacher" ? veto.request : undefined} />
        </div>
      ))}
      <div ref={sentinel} />
    </div>
  );
}

export default function Profile() {
  const { username = "" } = useParams<{ username: string }>();
  const [editing, setEditing] = useState(false);
  const q = useQuery({
    queryKey: ["profile", username],
    queryFn: () => api<ProfileHeader>(`/api/users/${encodeURIComponent(username)}`),
    retry: (n, err) => !(err instanceof ApiError && err.status === 404) && n < 2,
  });

  if (q.isPending) return <FeedSkeleton />;
  if (q.isError)
    return (
      <div className="flex flex-col items-center gap-3 p-6 text-center">
        <p className="text-muted-foreground">
          {q.error instanceof ApiError && q.error.status === 404 ? es.profile.notFound : es.feed.error}
        </p>
        <Link to="/" className="text-sm underline">{es.profile.backToFeed}</Link>
      </div>
    );

  const p = q.data;
  const grades = p.grades ?? [];
  return (
    <div className="flex flex-col">
      <header className="flex flex-col gap-2 p-4">
        <Avatar author={{ id: p.id, username: p.username, name: p.name,
                          avatar_url: p.avatar_url, role: p.role }} size={80} />
        <div>
          <p className="text-lg font-bold">{p.name}</p>
          <p className="text-sm text-muted-foreground">
            @{p.username}
            {p.role === "teacher" && <span className="ml-2 text-xs">{es.profile.teacherTag}</span>}
          </p>
        </div>
        {p.bio && <p className="whitespace-pre-wrap break-words text-sm">{p.bio}</p>}
        <p className="inline-flex items-center gap-1 text-sm text-muted-foreground">
          <RiSparkling2Line className="size-4" />
          {es.profile.auraReceived.replace("{n}", String(p.aura_received))}
        </p>
        {p.is_me && (
          <Button variant="outline" onClick={() => setEditing(true)}>{es.profile.editProfile}</Button>
        )}
        {!p.is_me && p.has_own_avatar && p.grades && (
          // Only a teacher who teaches this student receives `grades`.
          <RemovePhotoButton userId={p.id} />
        )}
      </header>

      {grades.length > 0 && (
        <section className="flex flex-col gap-2 border-y p-4">
          <h2 className="text-xs font-semibold uppercase text-muted-foreground">
            {es.profile.gradesTitle}
          </h2>
          {/* One or two classes at most: shown open, no hand-rolled
              disclosure widget (there is no preset for one). */}
          {grades.map((g) => (
            <div key={g.class_id} className="flex flex-col gap-1">
              <p className="flex justify-between text-sm">
                <span className="font-medium">{g.class_name}</span>
                <span className="font-semibold">{formatPoints(g.summary.total)}</span>
              </p>
              <GradeBreakdown grade={g.summary} />
            </div>
          ))}
          {p.is_me && <p className="text-xs text-muted-foreground">{es.profile.gradesPrivate}</p>}
        </section>
      )}

      <Tabs defaultValue="posts">
        <TabsList className="w-full">
          <TabsTrigger value="posts">{es.profile.tabPosts}</TabsTrigger>
          <TabsTrigger value="replies">{es.profile.tabReplies}</TabsTrigger>
        </TabsList>
        <TabsContent value="posts"><PostList username={p.username} tab="posts" /></TabsContent>
        <TabsContent value="replies"><PostList username={p.username} tab="replies" /></TabsContent>
      </Tabs>

      <Dialog open={editing} onOpenChange={setEditing}>
        <DialogContent>
          <DialogTitle>{es.profile.editProfile}</DialogTitle>
          <ProfileEditor onDone={() => { setEditing(false); void q.refetch(); }} />
        </DialogContent>
      </Dialog>
    </div>
  );
}
