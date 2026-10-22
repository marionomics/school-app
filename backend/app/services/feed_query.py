"""Turns the database into the plain facts feed_rank scores.

Every query is bounded by as_of, and window membership depends only on
created_at values, which never change — so every page of one load sees the
same ordered list.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Class, Enrollment, Like, Post, Review
from app.services.feed_rank import WINDOW_DAYS, Candidate, ReplyFact, rank
from app.services.visibility import ASSIGNMENT_TYPES, assignment_visible

ROOT_STATUSES = ("active", "vetoed")
PENDING_GRACE_DAYS = 14  # after a class ends, its pending work stays on top this long


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
    roots = (db.query(Post.id, Post.author_id, Post.created_at, Post.type)
             .filter(Post.id.in_(root_ids)).all())
    root_author = {r.id: r.author_id for r in roots}
    # Replies under a tarea or examen are homework, not conversation (spec
    # decision 8): they neither add activity nor lift the thread back up.
    social = [r.id for r in roots if r.type not in ASSIGNMENT_TYPES]
    cols = (Post.id, Post.parent_id, Post.author_id, Post.created_at, Post.status)
    level2 = db.query(*cols).filter(Post.parent_id.in_(social)).all() if social else []
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
                offset: int, limit: int,
                pending_at: Optional[Dict[int, datetime]] = None) -> Tuple[List[int], bool]:
    """One page of ids and whether more follow: the ranked window first
    (tiers — Bloque 4b), then every older root newest-first, so the feed never
    ends early. Pending roots join the window whatever their age."""
    pending_at = pending_at or {}
    win = sorted(set(window_ids(db, class_ids, as_of)) | set(pending_at))
    order = rank(load_candidates(db, win), viewer_id,
                 viewer_aura(db, viewer_id, win, as_of), as_of, pending_at)
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


def has_new(db: Session, viewer_id: int, class_ids: List[int], since: datetime) -> bool:
    """Something to show the "new posts" pill for: a visible root by someone
    else, or a reply by someone else in a thread the viewer is part of."""
    roots = (db.query(Post.id)
             .filter(Post.parent_id.is_(None), Post.status == "active",
                     Post.created_at > since, Post.author_id != viewer_id,
                     assignment_visible(class_ids)))
    if db.query(roots.exists()).scalar():
        return True
    mine = [pid for (pid,) in db.query(Post.id).filter(Post.author_id == viewer_id)]
    threads = set(root_ids_of(db, mine).values())
    # An entrega is homework, not a reply worth a pill (spec decision 8).
    if threads:
        threads = {pid for (pid,) in db.query(Post.id).filter(
            Post.id.in_(threads), Post.type.notin_(ASSIGNMENT_TYPES))}
    if not threads:
        return False
    level2 = {pid for (pid,) in db.query(Post.id).filter(Post.parent_id.in_(threads))}
    replies = (db.query(Post.id)
               .filter(Post.parent_id.in_(threads | level2), Post.created_at > since,
                       Post.author_id != viewer_id, Post.status == "active"))
    return bool(db.query(replies.exists()).scalar())


def teacher_pending(db: Session, teacher_id: int,
                    as_of: datetime) -> Dict[int, Tuple[datetime, Optional[int]]]:
    """root id → (pending since, count) for the work that needs this teacher,
    as of as_of. Same meaning as /revisar: a participación not validated nor
    vetoed; a tarea whose counting entrega from an active student has no
    review; an examen not calificado with something uploaded and ungraded.
    Participaciones carry no count."""
    # Only classes still running (plus a grace period for final grading): the
    # feed spans every semester, and last term's unreviewed work must not sit
    # above everything forever.
    still_running = (as_of - timedelta(days=PENDING_GRACE_DAYS)).date()
    class_ids = [cid for (cid,) in db.query(Class.id).filter(
        Class.teacher_id == teacher_id, Class.end_date >= still_running)]
    if not class_ids:
        return {}
    out: Dict[int, Tuple[datetime, Optional[int]]] = {}

    parts = (db.query(Post.id, Post.created_at)
             .filter(Post.class_id.in_(class_ids), Post.parent_id.is_(None),
                     Post.type == "participacion", Post.status == "active",
                     Post.created_at <= as_of,
                     or_(Post.reviewed_at.is_(None), Post.reviewed_at > as_of)))
    for pid, at in parts:
        out[pid] = (aware(at), None)

    items = (db.query(Post.id, Post.type, Post.class_id, Post.graded_at)
             .filter(Post.class_id.in_(class_ids), Post.parent_id.is_(None),
                     Post.type.in_(ASSIGNMENT_TYPES), Post.status == "active",
                     Post.created_at <= as_of).all())
    items = [i for i in items
             if i.type == "tarea" or i.graded_at is None or aware(i.graded_at) > as_of]
    if not items:
        return out
    active = {(cid, uid) for cid, uid in db.query(Enrollment.class_id, Enrollment.user_id)
              .filter(Enrollment.class_id.in_(class_ids), Enrollment.status == "active")}
    item_ids = [i.id for i in items]
    replies = (db.query(Post.id, Post.parent_id, Post.author_id, Post.created_at,
                        Post.is_entrega, Post.attachments.any().label("has_files"))
               .filter(Post.parent_id.in_(item_ids), Post.status == "active",
                       Post.created_at <= as_of).all())
    reviews = {(r.item_post_id, r.student_id): r
               for r in db.query(Review).filter(Review.item_post_id.in_(item_ids))}

    by_item = defaultdict(list)
    for r in replies:
        by_item[r.parent_id].append(r)

    for item in items:
        latest_entrega: Dict[int, tuple] = {}
        latest_upload: Dict[int, tuple] = {}
        for r in by_item[item.id]:
            if (item.class_id, r.author_id) not in active:
                continue
            at = aware(r.created_at)
            if r.is_entrega and (r.author_id not in latest_entrega
                                 or at > latest_entrega[r.author_id][1]):
                latest_entrega[r.author_id] = (r.id, at)
            if r.has_files and (r.author_id not in latest_upload
                                or at > latest_upload[r.author_id][1]):
                latest_upload[r.author_id] = (r.id, at)
        # An examen's submission is the entrega, else the latest reply with
        # files (the roster rule); a tarea's is only the entrega.
        subs = dict(latest_entrega)
        if item.type == "examen":
            for uid, v in latest_upload.items():
                subs.setdefault(uid, v)
        ungraded = []
        for uid, (sub_id, at) in subs.items():
            rv = reviews.get((item.id, uid))
            done = (rv is not None
                    and aware(rv.updated_at or rv.created_at) <= as_of
                    # counting_review: a review of a replaced entrega is stale.
                    and (rv.entrega_post_id is None or rv.entrega_post_id == sub_id)
                    and (item.type == "tarea" or rv.score is not None))
            if not done:
                ungraded.append(at)
        if ungraded:
            out[item.id] = (max(ungraded), len(ungraded))
    return out
