import { Link } from "react-router-dom";
import Avatar from "@/components/Avatar";
import {
  RiAttachment2,
  RiCheckLine,
  RiChat3Line,
  RiFileTextLine,
  RiHeart3Fill,
  RiHeart3Line,
  RiPushpinLine,
} from "@remixicon/react";
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
  onDelete,
  canDelete,
  onOpenAttachment,
}: {
  post: Post;
  onLike?: (post: Post) => void;
  linkToThread?: boolean;
  onDelete?: (post: Post) => void;
  canDelete?: boolean;
  onOpenAttachment?: (id: number) => void;
}) {
  // Only a DELETED post loses its body. A veto takes the points, not the
  // student's words — mirrors serialize_post on the backend, which stopped
  // blanking vetoed content. Treating vetoed as removed here would show the
  // author "[eliminado]" over a post that is still theirs and still visible.
  const removed = post.status === "deleted";
  const vetoed = post.status === "vetoed";
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
          {canDelete && (
            <button
              onClick={() => onDelete?.(post)}
              aria-label={es.post.deleteConfirm}
              className="ml-auto text-muted-foreground"
            >
              🗑
            </button>
          )}
        </div>
        {post.type === "participacion" && !removed && (
          <span className="mt-1 inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            <RiChat3Line className="size-3" /> {es.feed.participacionBadge}
            {post.taps && post.taps > 1 ? ` ×${post.taps}` : ""}
            {post.class_name ? ` · ${post.class_name}` : ""}
          </span>
        )}
        {post.type === "tarea" && !removed && (
          <span className="mt-1 inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-700">
            <RiPushpinLine className="size-3" /> {es.feed.tareaBadge}
            {post.due_date && ` · ${es.feed.dueOn.replace(
              "{date}", new Date(post.due_date).toLocaleDateString("es-MX"))}`}
          </span>
        )}
        {post.is_entrega && !removed && (
          <span className="mt-1 inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs font-medium text-emerald-700">
            <RiCheckLine className="size-3" /> {es.feed.entregaBadge}
          </span>
        )}
        {post.my_review?.score != null && !removed && (
          <span className="mt-1 inline-flex items-center gap-1 rounded-full bg-sky-500/15 px-2 py-0.5 text-xs font-medium text-sky-700">
            {es.post.scoreBadge.replace("{n}", String(post.my_review.score))}
          </span>
        )}
        {post.my_review?.feedback && !removed && (
          <p className="mt-1 rounded-lg bg-muted p-2 text-xs">
            <span className="font-medium">{es.post.feedbackFrom}: </span>
            {post.my_review.feedback}
          </p>
        )}
        {/* The notice does not depend on a reason: the reason is private to
            the author, so gating on it would leave a vetoed post looking
            entirely normal to everyone else — and to its own author whenever
            the teacher vetoed without typing one. */}
        {vetoed && (
          <p className="mt-1 text-xs text-destructive">
            {es.post.vetoedNotice}
            {post.veto_reason ? ` · ${post.veto_reason}` : ""}
          </p>
        )}
        {post.type === "examen" && !removed && (
          <span className="mt-1 inline-flex items-center gap-1 rounded-full bg-violet-500/15 px-2 py-0.5 text-xs font-medium text-violet-700">
            <RiFileTextLine className="size-3" /> {es.post.examenBadge}
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
            {post.attachments.map((a) =>
              onOpenAttachment ? (
                <button
                  key={a.id}
                  onClick={() => onOpenAttachment(a.id)}
                  className="inline-flex items-center gap-1 border px-2 py-1 text-xs"
                >
                  <RiAttachment2 className="size-3" /> {a.file_name}
                </button>
              ) : (
                <span
                  key={a.id}
                  className="inline-flex items-center gap-1 border px-2 py-1 text-xs"
                >
                  <RiAttachment2 className="size-3" /> {a.file_name}
                </span>
              ),
            )}
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
            {post.liked_by_me ? (
              <RiHeart3Fill className="size-4" />
            ) : (
              <RiHeart3Line className="size-4" />
            )}
            {post.like_count > 0 ? post.like_count : ""}
          </button>
          <span>
            💬 {post.reply_count > 0 ? post.reply_count : ""}
          </span>
        </div>
      </div>
    </article>
  );
}
