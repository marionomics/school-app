import type { Author, Mention, Post } from "./types";

/** Same rule as backend/app/services/mentions.py. No lookbehind: iOS Safari
 *  before 16.4 throws on it when the module loads. The leading group eats
 *  the character before the @ instead. */
export const MENTION_SOURCE = "(^|[^A-Za-z0-9_@])@([A-Za-z0-9_]{3,20})(?![A-Za-z0-9_])";

export type Segment = { text: string } | { mention: Author };

export function parseUsernames(content: string): string[] {
  const out: string[] = [];
  for (const m of content.matchAll(new RegExp(MENTION_SOURCE, "g"))) {
    const name = m[2].toLowerCase();
    if (!out.includes(name)) out.push(name);
  }
  return out;
}

export function splitMentions(content: string, mentions: Mention[] = []): Segment[] {
  const byName = new Map(
    mentions
      .filter((x) => x.user.username)
      .map((x) => [x.user.username!.toLowerCase(), x.user]),
  );
  const out: Segment[] = [];
  let last = 0;
  for (const m of content.matchAll(new RegExp(MENTION_SOURCE, "g"))) {
    const user = byName.get(m[2].toLowerCase());
    if (!user) continue;
    const at = m.index! + m[1].length;
    if (at > last) out.push({ text: content.slice(last, at) });
    out.push({ mention: user });
    last = at + 1 + m[2].length;
  }
  if (last < content.length || out.length === 0) out.push({ text: content.slice(last) });
  return out;
}

/** The @word being typed at the caret, if any. */
export function activeMention(
  value: string,
  caret: number,
): { start: number; query: string } | null {
  let i = caret - 1;
  while (i >= 0 && /[A-Za-z0-9_]/.test(value[i])) i--;
  if (i < 0 || value[i] !== "@") return null;
  if (i > 0 && /[A-Za-z0-9_@]/.test(value[i - 1])) return null;
  const query = value.slice(i + 1, caret);
  if (query.length < 1 || query.length > 20) return null;
  return { start: i, query };
}

export function insertMention(
  value: string,
  start: number,
  caret: number,
  username: string,
): { value: string; caret: number } {
  const inserted = `@${username} `;
  return {
    value: value.slice(0, start) + inserted + value.slice(caret),
    caret: start + inserted.length,
  };
}

/** Members a submission still counts for, besides its author. */
export function liveTeam(post: Pick<Post, "mentions">): Author[] {
  return (post.mentions ?? [])
    .filter((x) => x.kind === "team" && !x.removed)
    .map((x) => x.user);
}
