import { Link } from "react-router-dom";
import Avatar from "@/components/Avatar";
import { es } from "@/strings/es";
import type { Post } from "@/lib/types";

function timeAgo(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "ahora";
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

export default function PostCard({
  post,
  onLike,
  linkToThread = true,
}: {
  post: Post;
  onLike?: (post: Post) => void;
  linkToThread?: boolean;
}) {
  const removed = post.status !== "active";
  const body = removed ? (
    <p className="italic text-muted-foreground">{es.feed.deletedPost}</p>
  ) : (
    <p className="whitespace-pre-wrap break-words">{post.content}</p>
  );
  return (
    <article className="flex gap-3 p-4">
      <Avatar author={post.author} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-sm">
          <span className="font-semibold">@{post.author.username ?? post.author.name}</span>
          {post.author.role === "teacher" && <span aria-hidden>👨‍🏫</span>}
          <span className="text-muted-foreground">{timeAgo(post.created_at)}</span>
        </div>
        {post.type === "participacion" && !removed && (
          <span className="mt-1 inline-block rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            🗣️ {es.feed.participacionBadge}
            {post.taps && post.taps > 1 ? ` ×${post.taps}` : ""}
            {post.class_name ? ` · ${post.class_name}` : ""}
          </span>
        )}
        {linkToThread && !removed ? (
          <Link to={`/post/${post.id}`} className="mt-1 block">
            {body}
          </Link>
        ) : (
          <div className="mt-1">{body}</div>
        )}
        {!removed && post.attachments.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {post.attachments.map((a) => (
              <span key={a.id} className="rounded-md border px-2 py-1 text-xs">
                📎 {a.file_name}
              </span>
            ))}
          </div>
        )}
        <div className="mt-2 flex items-center gap-5 text-sm text-muted-foreground">
          <button
            onClick={() => onLike?.(post)}
            disabled={!onLike || removed}
            aria-label={post.liked_by_me ? es.feed.unlike : es.feed.like}
            aria-pressed={post.liked_by_me}
            className={post.liked_by_me ? "text-destructive" : ""}
          >
            {post.liked_by_me ? "♥" : "♡"} {post.like_count > 0 ? post.like_count : ""}
          </button>
          <span>
            💬 {post.reply_count > 0 ? post.reply_count : ""}
          </span>
        </div>
      </div>
    </article>
  );
}
