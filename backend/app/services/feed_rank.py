"""Per-viewer feed ranking (Bloque 4).

Pure functions over plain data — no ORM, no database — tested like the grade
engine. What you touched sinks for you; a conversation you are in comes back
when it moves. The weights are starting points to tune with data
(scripts/feed_metrics.py), not results of a calculation.
"""
from dataclasses import dataclass
from datetime import datetime
from math import log1p
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

HALF_LIFE_H = 24.0      # a post's freshness halves every day
W_FRESH = 1.0           # a brand-new post scores 1.0
W_ACTIVITY = 0.4        # log1p, so a 30-reply thread does not own the feed
AURA_FACTOR = 0.5       # aura: the post is one day older for you
REPLY_FACTOR = 0.125    # reply or authorship: three days older for you
W_LIFT = 1.5            # a fresh reply to you beats a brand-new post
LIFT_TO_ME = 1.0
LIFT_IN_THREAD = 0.25
WINDOW_DAYS = 14        # older posts without recent replies go to the tail


@dataclass(frozen=True)
class ReplyFact:
    author_id: int
    created_at: datetime
    parent_author_id: int   # author of the post it answers
    active: bool            # status == "active"


@dataclass(frozen=True)
class Candidate:
    post_id: int
    author_id: int
    created_at: datetime
    replies: Tuple[ReplyFact, ...] = ()


def decay(hours: float) -> float:
    return 0.5 ** (max(0.0, hours) / HALF_LIFE_H)


def _age(as_of: datetime, dt: datetime) -> float:
    return (as_of - dt).total_seconds() / 3600


def score(c: Candidate, viewer_id: int, aura_at: Optional[datetime],
          as_of: datetime) -> float:
    replies = [r for r in c.replies if r.created_at <= as_of]
    if aura_at is not None and aura_at > as_of:
        aura_at = None
    my_replies = [r.created_at for r in replies if r.author_id == viewer_id]
    authored = c.author_id == viewer_id
    # Replying (or authoring) subscribes you to the thread; aura never does.
    subscribed = authored or bool(my_replies)
    others = [r for r in replies if r.active and r.author_id != viewer_id]

    base = (W_FRESH * decay(_age(as_of, c.created_at))
            + W_ACTIVITY * log1p(sum(decay(_age(as_of, r.created_at)) for r in others)))
    if subscribed:
        factor = REPLY_FACTOR
    elif aura_at is not None:
        factor = AURA_FACTOR
    else:
        factor = 1.0

    touches = my_replies + ([c.created_at] if authored else []) + ([aura_at] if aura_at else [])
    lift = 0.0
    if touches:
        last = max(touches)
        for r in others:
            if r.created_at <= last:
                continue
            if r.parent_author_id == viewer_id:
                lift += LIFT_TO_ME * decay(_age(as_of, r.created_at))
            elif subscribed:
                lift += LIFT_IN_THREAD * decay(_age(as_of, r.created_at))
    return base * factor + W_LIFT * log1p(lift)


def rank(candidates: Iterable[Candidate], viewer_id: int,
         aura_at: Dict[int, datetime], as_of: datetime) -> List[int]:
    """Post ids, best first. Ties break on post id descending, so the order
    is total and the same on every page of one load."""
    scored = [(score(c, viewer_id, aura_at.get(c.post_id), as_of), c.post_id)
              for c in candidates]
    scored.sort(key=lambda t: (-t[0], -t[1]))
    return [pid for _, pid in scored]


@dataclass(frozen=True)
class ReplyOption:
    post_id: int
    created_at: datetime
    like_count: int
    teacher_aura: bool


def pick_featured(options: Sequence[ReplyOption]) -> Optional[int]:
    """The comment shown under a card: one the teacher gave aura, then the
    most aura, then the most recent. The caller passes only eligible replies."""
    if not options:
        return None
    best = max(options, key=lambda o: (o.teacher_aura, o.like_count, o.created_at, o.post_id))
    return best.post_id
