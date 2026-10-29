import UserLink from "@/components/UserLink";
import { splitMentions } from "@/lib/mentions";
import type { Mention } from "@/lib/types";

/** Post text with each resolved @mention as a UserLink. An @word the server
 *  didn't resolve stays text — never a dead link. The span stops the tap from
 *  also reaching a card-level "open thread" handler. */
export default function MentionText({
  content,
  mentions,
}: {
  content: string;
  mentions?: Mention[];
}) {
  return (
    <>
      {splitMentions(content, mentions).map((s, i) =>
        "mention" in s ? (
          <span key={i} onClick={(e) => e.stopPropagation()}>
            <UserLink user={s.mention} className="font-medium" />
          </span>
        ) : (
          <span key={i}>{s.text}</span>
        ),
      )}
    </>
  );
}
