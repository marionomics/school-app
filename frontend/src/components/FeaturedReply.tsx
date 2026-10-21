import { Link } from "react-router-dom";
import { RiSparkling2Line } from "@remixicon/react";
import UserLink from "@/components/UserLink";
import { es } from "@/strings/es";
import type { Post } from "@/lib/types";

/** The one comment shown under a feed card (Bloque 4). Read-only: aura and
 *  replies happen in the thread, so a tap here opens it. */
export default function FeaturedReply({
  reply,
  rootId,
  replyCount,
}: {
  reply: Post;
  rootId: number;
  replyCount: number;
}) {
  // 68px = the card's padding (16) + avatar (40) + gap (12): it lines up
  // with the card's text column.
  return (
    <div className="-mt-2 mb-3 ml-[68px] mr-4 border-l-2 pl-3 text-sm">
      <div className="flex items-center gap-2">
        <UserLink user={reply.author} className="font-semibold" />
        {reply.author.role === "teacher" && (
          <span className="text-xs text-muted-foreground">{es.feed.teacherTag}</span>
        )}
        {reply.like_count > 0 && (
          <span className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground">
            <RiSparkling2Line className="size-3" />
            {reply.like_count}
            {reply.teacher_aura && ` · ${es.feed.teacherAura}`}
          </span>
        )}
      </div>
      <Link to={`/post/${rootId}`} className="mt-0.5 block">
        <p className="line-clamp-2 whitespace-pre-wrap break-words">{reply.content}</p>
      </Link>
      {replyCount > 1 && (
        <Link to={`/post/${rootId}`} className="mt-1 block text-xs text-muted-foreground">
          {es.feed.seeAllReplies.replace("{n}", String(replyCount))}
        </Link>
      )}
    </div>
  );
}
