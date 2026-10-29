"""Which submission counts for a student on a tarea or examen.

A student's submission is their own, or a team one that names them (spec
2026-10-28-menciones-equipos §2). grades._counting_entrega and
grades.examen_submission delegate here, so the engine, /revisar, the feed and
the thread can never disagree. The two places that inline this rule for speed
(feed_query.teacher_pending, the thread) have agreement tests.
"""
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models import Post, PostMention


def own_entrega(db: Session, user_id: int, item_id: int) -> Optional[Post]:
    """Latest active entrega this student wrote on this item."""
    return (
        db.query(Post)
        .filter(Post.author_id == user_id,
                Post.parent_id == item_id,
                Post.is_entrega.is_(True),
                Post.status == "active")
        .order_by(Post.created_at.desc(), Post.id.desc())
        .first()
    )


def own_submission(db: Session, user_id: int, item: Post) -> Optional[Post]:
    """What this student handed in themselves. For an examen: their entrega,
    else their latest reply with files — nobody tells a student to flip the
    entrega toggle on an examen (bug 8); a text-only reply is a question."""
    entrega = own_entrega(db, user_id, item.id)
    if entrega is not None or item.type != "examen":
        return entrega
    return (
        db.query(Post)
        .filter(Post.author_id == user_id,
                Post.parent_id == item.id,
                Post.status == "active",
                Post.attachments.any())
        .order_by(Post.created_at.desc(), Post.id.desc())
        .first()
    )


def _is_live(db: Session, post: Post, item: Post) -> bool:
    """A team submission counts only while it is its author's current one: if
    Ana replaces her entrega, she replaces it for the whole team."""
    current = own_submission(db, post.author_id, item)
    return current is not None and current.id == post.id


def live_team_submissions(db: Session, user_id: int, item: Post,
                          entrega_only: bool = False) -> List[Post]:
    q = (db.query(Post)
         .join(PostMention, PostMention.post_id == Post.id)
         .filter(PostMention.user_id == user_id,
                 PostMention.kind == "team",
                 PostMention.removed_at.is_(None),
                 Post.parent_id == item.id,
                 Post.status == "active"))
    if entrega_only:
        q = q.filter(Post.is_entrega.is_(True))
    return [p for p in q.all() if _is_live(db, p, item)]


def _newest(posts: Iterable[Optional[Post]]) -> Optional[Post]:
    found = [p for p in posts if p is not None]
    if not found:
        return None
    return max(found, key=lambda p: (p.created_at, p.id))


def counting_entrega(db: Session, user_id: int, item_id: int) -> Optional[Post]:
    """The entrega that counts for this student: the newest of their own and
    the live team entregas naming them."""
    own = own_entrega(db, user_id, item_id)
    item = db.get(Post, item_id)
    if item is None:
        return own
    return _newest([own, *live_team_submissions(db, user_id, item, entrega_only=True)])


def counting_submission(db: Session, user_id: int, item: Post) -> Optional[Post]:
    """Like counting_entrega, with the examen rule for what a submission is."""
    return _newest([own_submission(db, user_id, item),
                    *live_team_submissions(db, user_id, item)])


def live_team_member_ids(db: Session, post: Post) -> List[int]:
    """Who this submission counts for besides its author, right now."""
    if post.parent_id is None or post.status != "active":
        return []
    item = db.get(Post, post.parent_id)
    if item is None or not _is_live(db, post, item):
        return []
    return [m.user_id for m in post.mentions
            if m.kind == "team" and m.removed_at is None]


def team_of(db: Session, user_id: int, item: Post,
            ignore_author: Optional[int] = None) -> Optional[Post]:
    """The live team submission this student is already on for this item —
    as a member, or as the author of one with members. `ignore_author` lets an
    author re-tag their own team in a new version (the team carries over)."""
    for p in live_team_submissions(db, user_id, item):
        if p.author_id != ignore_author:
            return p
    if user_id == ignore_author:
        return None
    own = own_submission(db, user_id, item)
    if own is not None and live_team_member_ids(db, own):
        return own
    return None
