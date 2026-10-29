import { es } from "../strings/es";
import { liveTeam } from "./mentions";
import type { Post, TeamCheckResult } from "./types";

/** The warning under the submission composer for one @, or null if it joins
 *  (or is the author — nothing to say). Warnings never block sending. */
export function teamWarning(r: TeamCheckResult): string | null {
  const t = es.mentions;
  const fill = (s: string) =>
    s.replace("{user}", r.username).replace("{author}", r.team_author ?? "");
  switch (r.status) {
    case "ok":
    case "self":
      return null;
    case "max_team":
      return fill(t.maxTeam);
    case "not_in_class":
      return fill(t.notInClass);
    case "on_team":
      return fill(t.onTeam);
    case "unknown":
      return fill(t.unknown);
    case "author_inactive":
      return t.authorInactive;
  }
}

/** Publish re-decides the team; if it differs from the last check, say who
 *  ended up on it. */
export function teamResultToast(expected: string[], sent: Post): string | null {
  const got = liveTeam(sent).map((u) => u.username ?? "");
  const same =
    got.length === expected.length && got.every((u) => expected.includes(u));
  if (same) return null;
  if (got.length === 0) return es.mentions.teamAlone;
  return es.mentions.teamResult.replace("{users}", got.map((u) => `@${u}`).join(" · "));
}
