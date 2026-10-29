"""@mentions: parsing, and deciding who a submission's team is.

Spec: docs/superpowers/specs/2026-10-28-menciones-equipos-design.md
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Enrollment, Post, PostMention, User
from app.services.submissions import team_of

# The UserUpdate username pattern. Not preceded by a word character, so an
# email address is not a mention; not followed by one, so @ + 21 letters is
# not a truncated username.
MENTION_RE = re.compile(r"(?<![A-Za-z0-9_@])@([A-Za-z0-9_]{3,20})(?![A-Za-z0-9_])")


def parse_usernames(content: str) -> List[str]:
    out: List[str] = []
    for m in MENTION_RE.finditer(content or ""):
        name = m.group(1).lower()
        if name not in out:
            out.append(name)
    return out


MAX_TEAM = 2


@dataclass
class TeamVerdict:
    username: str
    user: Optional[User]
    reason: Optional[str]            # None = joins the team
    team_author: Optional[User] = None


def _active_ids(db: Session, class_id: int) -> set:
    return {uid for (uid,) in db.query(Enrollment.user_id).filter(
        Enrollment.class_id == class_id, Enrollment.status == "active")}


def evaluate_team(db: Session, author: User, item: Post,
                  usernames: List[str]) -> List[TeamVerdict]:
    """Who a submission's @mentions make part of the team, in the order written.
    Used by publish (which stores the result) and by team-check (read-only)."""
    users = {u.username: u for u in db.query(User).filter(User.username.in_(usernames))} \
        if usernames else {}
    active = _active_ids(db, item.class_id)
    author_active = author.id in active
    out: List[TeamVerdict] = []
    joined = 0
    for name in usernames:
        u = users.get(name)
        if u is None:
            out.append(TeamVerdict(name, None, "unknown"))
        elif u.id == author.id:
            out.append(TeamVerdict(name, u, "self"))
        elif not author_active:
            out.append(TeamVerdict(name, u, "author_inactive"))
        elif u.id not in active:
            out.append(TeamVerdict(name, u, "not_in_class"))
        else:
            other = team_of(db, u.id, item, ignore_author=author.id)
            if other is not None:
                out.append(TeamVerdict(name, u, "on_team", team_author=other.author))
            elif joined >= MAX_TEAM:
                out.append(TeamVerdict(name, u, "max_team"))
            else:
                joined += 1
                out.append(TeamVerdict(name, u, None))
    return out


def record_mentions(db: Session, post: Post, author: User, item: Optional[Post]) -> None:
    """Store every @mention of a freshly flushed post. `item` is the tarea or
    examen when the post is a submission; then eligible mentions are 'team'.
    Decided once, never recomputed (first team wins must not flip later)."""
    names = parse_usernames(post.content)
    if not names:
        return
    if item is not None:
        verdicts = evaluate_team(db, author, item, names)
    else:
        found = {u.username: u for u in db.query(User).filter(User.username.in_(names))}
        verdicts = [TeamVerdict(n, found.get(n), "social") for n in names]
    for v in verdicts:
        if v.user is None or v.user.id == author.id:
            continue
        db.add(PostMention(post_id=post.id, user_id=v.user.id,
                           kind="team" if v.reason is None else "social"))
