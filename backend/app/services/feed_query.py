"""Turns the database into the plain facts feed_rank scores.

Every query is bounded by as_of, and window membership depends only on
created_at values, which never change — so every page of one load sees the
same ordered list.
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Tuple

from sqlalchemy.orm import Session

from app.models import Like, Post
from app.services.feed_rank import WINDOW_DAYS, Candidate, ReplyFact, rank
from app.services.visibility import assignment_visible

ROOT_STATUSES = ("active", "vetoed")


def aware(dt: datetime) -> datetime:
    """SQLite hands back naive datetimes; everything stored is UTC."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def root_ids_of(db: Session, post_ids: Iterable[int]) -> Dict[int, int]:
    """post id → its thread's root id. Threads are at most three levels."""
    ids = set(post_ids)
    if not ids:
        return {}
    parent = dict(db.query(Post.id, Post.parent_id).filter(Post.id.in_(ids)).all())
    need = {p for p in parent.values() if p is not None}
    grand = dict(db.query(Post.id, Post.parent_id).filter(Post.id.in_(need)).all()) if need else {}
    out = {}
    for pid, par in parent.items():
        if par is None:
            out[pid] = pid
        elif grand.get(par) is None:
            out[pid] = par
        else:
            out[pid] = grand[par]
    return out


def _roots(db: Session, class_ids: List[int], as_of: datetime):
    return (db.query(Post.id)
            .filter(Post.parent_id.is_(None), Post.status.in_(ROOT_STATUSES),
                    assignment_visible(class_ids), Post.created_at <= as_of))


def window_ids(db: Session, class_ids: List[int], as_of: datetime) -> List[int]:
    """Roots created in the window, plus roots with a reply created in it."""
    start = as_of - timedelta(days=WINDOW_DAYS)
    new = {pid for (pid,) in _roots(db, class_ids, as_of).filter(Post.created_at >= start)}
    recent = [pid for (pid,) in db.query(Post.id).filter(
        Post.parent_id.isnot(None), Post.created_at >= start, Post.created_at <= as_of)]
    revived = set(root_ids_of(db, recent).values())
    if revived:
        revived = {pid for (pid,) in _roots(db, class_ids, as_of).filter(Post.id.in_(revived))}
    return sorted(new | revived)


def load_candidates(db: Session, root_ids: List[int]) -> List[Candidate]:
    if not root_ids:
        return []
    roots = db.query(Post.id, Post.author_id, Post.created_at).filter(Post.id.in_(root_ids)).all()
    root_author = {r.id: r.author_id for r in roots}
    cols = (Post.id, Post.parent_id, Post.author_id, Post.created_at, Post.status)
    level2 = db.query(*cols).filter(Post.parent_id.in_(root_ids)).all()
    l2_root = {r.id: r.parent_id for r in level2}
    l2_author = {r.id: r.author_id for r in level2}
    level3 = db.query(*cols).filter(Post.parent_id.in_(list(l2_root))).all() if l2_root else []
    facts: Dict[int, list] = {pid: [] for pid in root_ids}
    for r in level2:
        facts[r.parent_id].append(ReplyFact(r.author_id, aware(r.created_at),
                                            root_author[r.parent_id], r.status == "active"))
    for r in level3:
        facts[l2_root[r.parent_id]].append(ReplyFact(r.author_id, aware(r.created_at),
                                                     l2_author[r.parent_id], r.status == "active"))
    return [Candidate(r.id, r.author_id, aware(r.created_at), tuple(facts[r.id])) for r in roots]


def viewer_aura(db: Session, viewer_id: int, root_ids: List[int],
                as_of: datetime) -> Dict[int, datetime]:
    if not root_ids:
        return {}
    rows = (db.query(Like.post_id, Like.created_at)
            .filter(Like.user_id == viewer_id, Like.post_id.in_(root_ids),
                    Like.created_at <= as_of).all())
    return {pid: aware(at) for pid, at in rows}


def ranked_page(db: Session, viewer_id: int, class_ids: List[int], as_of: datetime,
                offset: int, limit: int) -> Tuple[List[int], bool]:
    """One page of ids and whether more follow: the ranked window first,
    then every older root newest-first, so the feed never ends early."""
    win = window_ids(db, class_ids, as_of)
    order = rank(load_candidates(db, win), viewer_id, viewer_aura(db, viewer_id, win, as_of), as_of)
    page = order[offset:offset + limit + 1]
    need = limit + 1 - len(page)
    if need > 0:
        tail = _roots(db, class_ids, as_of)
        if win:
            tail = tail.filter(Post.id.notin_(win))
        tail = (tail.order_by(Post.created_at.desc(), Post.id.desc())
                .offset(max(0, offset - len(order))).limit(need))
        page += [pid for (pid,) in tail]
    return page[:limit], len(page) > limit
