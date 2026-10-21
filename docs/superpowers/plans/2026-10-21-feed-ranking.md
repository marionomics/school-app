# Bloque 4 — Feed Ranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rank the feed per viewer (what you touched sinks, a conversation you're in comes back), freeze the order per load, show one featured comment under each card, and tell the reader when something new exists instead of reordering under them.

**Architecture:** A pure scoring module (`feed_rank.py`) ranks plain dataclasses; a DB module (`feed_query.py`) turns tables into those facts, always bounded by `as_of`. `GET /api/feed` pages by `{as_of, offset}` over "ranked window, then chronological tail". The client stops refetching the feed on its own; three explicit actions reset it to page 1, and every other screen patches the cache.

**Tech Stack:** FastAPI, SQLAlchemy, pytest (CI on PostgreSQL); React, TanStack Query v5, Vitest, Tailwind, `@remixicon/react`.

**Spec:** `docs/superpowers/specs/2026-10-21-feed-ranking-design.md`

## Global Constraints

- No new tables, no migration.
- The class filter is `assignment_visible(viewer_class_ids(db, user))` from `backend/app/services/visibility.py` — every feed query uses it.
- Root candidates have `status IN ('active','vetoed')`; vetoed posts stay in the feed.
- Pinned tareas (`_pinned_tareas`) are unchanged and stay outside pagination.
- Aura and veto from the feed never refetch the feed (they already patch the cache via `patchPostInCaches`).
- The feed query is refetched only by `refreshFeed(qc)`; no other code may `invalidateQueries({queryKey: ["feed"]})`.
- Every username/avatar goes through `UserLink`; icons from `@remixicon/react`; all copy goes in `frontend/src/strings/es.ts` as placeholders (Mario writes final copy, tú not usted).
- Use preset components (`@/components/ui/button`); never restyle a primitive.
- Implementers commit, **never push**. The controller pushes after a clean review (every push deploys to students).
- Backend tests: `cd backend && pytest tests -q`. Frontend: `cd frontend && npm run lint && npm run typecheck && npm test`.

## Review Focus

1. **A featured reply under a tarea/examen** would expose homework answers to the whole feed → never featured for those root types (test in Task 4).
2. **Mixed `as_of` across pages** — TanStack refetching all stored pages after an invalidate would pair a new first page with old cursors → `refreshFeed` truncates to the first page before invalidating (test in Task 6).
3. **Timezone-naive datetimes from SQLite** compared with aware `as_of` → `aware()` normalizes every datetime entering `feed_rank` (test in Task 3 runs on SQLite locally and Postgres in CI).
4. **A deleted root still in the cached feed** after deleting it from its thread → `dropFromFeed` (test in Task 6).
5. **`has-new` with `since` containing `+00:00`** unencoded in a URL turns `+` into a space → the client uses `encodeURIComponent`, the server rejects naive/unparseable values with 422 (test in Task 5).

---

### Task 1: Pure ranking — `feed_rank.score` and `rank`

**Files:**
- Create: `backend/app/services/feed_rank.py`
- Test: `backend/tests/test_feed_rank.py`

**Interfaces:**
- Produces: `ReplyFact(author_id:int, created_at:datetime, parent_author_id:int, active:bool)`, `Candidate(post_id:int, author_id:int, created_at:datetime, replies:Tuple[ReplyFact,...]=())`, `decay(hours:float)->float`, `score(c:Candidate, viewer_id:int, aura_at:Optional[datetime], as_of:datetime)->float`, `rank(candidates:Iterable[Candidate], viewer_id:int, aura_at:Dict[int,datetime], as_of:datetime)->List[int]`, constants `HALF_LIFE_H, W_FRESH, W_ACTIVITY, AURA_FACTOR, REPLY_FACTOR, W_LIFT, LIFT_TO_ME, LIFT_IN_THREAD, WINDOW_DAYS`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_feed_rank.py
from datetime import datetime, timedelta, timezone

import pytest

from app.services.feed_rank import Candidate, ReplyFact, rank, score

AS_OF = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
ME, ANA, LUIS = 1, 2, 3


def ago(hours):
    return AS_OF - timedelta(hours=hours)


def post(pid, author=ANA, age=0, replies=()):
    return Candidate(pid, author, ago(age), tuple(replies))


def reply(author, age, parent_author=ANA, active=True):
    return ReplyFact(author, ago(age), parent_author, active)


def test_newer_beats_older():
    assert rank([post(1, age=10), post(2, age=1)], ME, {}, AS_OF) == [2, 1]


def test_ties_break_on_post_id_descending():
    assert rank([post(1), post(2)], ME, {}, AS_OF) == [2, 1]


def test_aura_sinks_by_exactly_one_half_life():
    liked = score(post(1, age=0), ME, ago(0), AS_OF)
    day_old = score(post(2, age=24), ME, None, AS_OF)
    assert liked == pytest.approx(day_old)


def test_a_reply_sinks_by_three_half_lives():
    replied = score(post(1, age=0, replies=[reply(ME, 0)]), ME, None, AS_OF)
    # Activity from the viewer's own reply never counts, so only freshness is left.
    assert replied == pytest.approx(score(post(2, age=72), ME, None, AS_OF))


def test_authoring_counts_as_a_reply():
    mine = score(post(1, author=ME, age=0), ME, None, AS_OF)
    assert mine == pytest.approx(score(post(2, age=72), ME, None, AS_OF))


def test_a_reply_to_me_brings_my_post_above_a_fresh_one():
    mine = post(1, author=ME, age=48, replies=[reply(ANA, 0, parent_author=ME)])
    fresh = post(2, author=LUIS, age=0)
    assert rank([fresh, mine], ME, {}, AS_OF) == [1, 2]


def test_a_reply_in_my_thread_lifts_less_than_a_reply_to_me():
    # I commented on Luis's post; Ana then answers either me or Luis.
    to_me = post(1, author=LUIS, age=48,
                 replies=[reply(ME, 30, parent_author=LUIS), reply(ANA, 0, parent_author=ME)])
    in_thread = post(2, author=LUIS, age=48,
                     replies=[reply(ME, 30, parent_author=LUIS), reply(ANA, 0, parent_author=LUIS)])
    assert score(to_me, ME, None, AS_OF) > score(in_thread, ME, None, AS_OF)
    untouched_lift = score(post(3, author=LUIS, age=48,
                                replies=[reply(ME, 30, parent_author=LUIS)]), ME, None, AS_OF)
    assert score(in_thread, ME, None, AS_OF) > untouched_lift


def test_aura_alone_does_not_subscribe():
    c = post(1, age=10, replies=[reply(LUIS, 0)])
    with_aura = score(c, ME, ago(5), AS_OF)
    without = score(c, ME, None, AS_OF)
    assert with_aura == pytest.approx(without * 0.5)


def test_replies_before_my_touch_do_not_lift():
    c = post(1, author=LUIS, age=48,
             replies=[reply(ANA, 40, parent_author=ME), reply(ME, 30, parent_author=LUIS)])
    # Ana's reply predates my last touch, so it only adds activity.
    assert score(c, ME, None, AS_OF) < score(post(2, age=0), ME, None, AS_OF)


def test_my_own_replies_are_not_activity():
    lonely = score(post(1, age=5), ME, None, AS_OF)
    busy_with_me = score(post(1, age=5, replies=[reply(ME, 1)] * 5), ME, None, AS_OF)
    assert busy_with_me < lonely  # only the penalty applied, no activity gained


def test_inactive_replies_count_for_nothing():
    plain = score(post(1, age=5), ME, None, AS_OF)
    gone = score(post(1, age=5, replies=[reply(ANA, 1, active=False)]), ME, None, AS_OF)
    assert gone == pytest.approx(plain)


def test_activity_is_concave():
    one = score(post(1, age=5, replies=[reply(ANA, 1)]), ME, None, AS_OF)
    thirty = score(post(1, age=5, replies=[reply(ANA, 1)] * 30), ME, None, AS_OF)
    assert thirty < one * 5


def test_touches_and_replies_after_as_of_are_ignored():
    c = post(1, age=5, replies=[ReplyFact(ANA, AS_OF + timedelta(minutes=1), ANA, True)])
    assert score(c, ME, AS_OF + timedelta(minutes=1), AS_OF) == pytest.approx(
        score(post(1, age=5), ME, None, AS_OF))
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && pytest tests/test_feed_rank.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.feed_rank'`

- [ ] **Step 3: Implement**

```python
# backend/app/services/feed_rank.py
"""Per-viewer feed ranking (Bloque 4).

Pure functions over plain data — no ORM, no database — tested like the grade
engine. What you touched sinks for you; a conversation you are in comes back
when it moves. The weights are starting points to tune with data
(scripts/feed_metrics.py), not results of a calculation.
"""
from dataclasses import dataclass
from datetime import datetime
from math import log1p
from typing import Dict, Iterable, List, Optional, Tuple

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
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd backend && pytest tests/test_feed_rank.py -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/feed_rank.py backend/tests/test_feed_rank.py
git commit -m "feat(feed): pure per-viewer ranking"
```

---

### Task 2: Pure featured-reply ladder — `pick_featured`

**Files:**
- Modify: `backend/app/services/feed_rank.py` (append)
- Test: `backend/tests/test_feed_rank.py` (append)

**Interfaces:**
- Produces: `ReplyOption(post_id:int, created_at:datetime, like_count:int, teacher_aura:bool)`, `pick_featured(options:Sequence[ReplyOption]) -> Optional[int]`. Callers pass only eligible replies (level 2, active, under a regular/participación root) — Task 4 filters.

- [ ] **Step 1: Write the failing tests**

```python
# append to backend/tests/test_feed_rank.py
from app.services.feed_rank import ReplyOption, pick_featured


def opt(pid, age=0, likes=0, teacher=False):
    return ReplyOption(pid, ago(age), likes, teacher)


def test_no_replies_no_featured():
    assert pick_featured([]) is None


def test_teacher_aura_beats_more_aura():
    assert pick_featured([opt(1, likes=9), opt(2, likes=1, teacher=True)]) == 2


def test_more_aura_beats_recency():
    assert pick_featured([opt(1, age=0, likes=1), opt(2, age=5, likes=3)]) == 2


def test_recency_breaks_an_aura_tie():
    assert pick_featured([opt(1, age=5, likes=2), opt(2, age=1, likes=2)]) == 2


def test_id_breaks_a_full_tie():
    assert pick_featured([opt(1), opt(2)]) == 2
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && pytest tests/test_feed_rank.py -q`
Expected: FAIL — `ImportError: cannot import name 'ReplyOption'`

- [ ] **Step 3: Implement** (append to `feed_rank.py`; add `Sequence` to the `typing` import)

```python
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
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd backend && pytest tests/test_feed_rank.py -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/feed_rank.py backend/tests/test_feed_rank.py
git commit -m "feat(feed): featured-reply ladder"
```

---

### Task 3: Ranked pagination — `feed_query.py`, feed cursor, `GET /api/feed`

**Files:**
- Create: `backend/app/services/feed_query.py`
- Modify: `backend/app/services/cursor.py` (add feed cursor; keep `encode_cursor`/`decode_cursor` for profiles)
- Modify: `backend/app/routers/posts.py` (`get_feed`, lines ~166–204)
- Test: `backend/tests/test_feed.py` (replace `test_feed_orders_by_activity_and_paginates`; keep the rest), create `backend/tests/test_feed_ranking_api.py`

**Interfaces:**
- Consumes: `Candidate`, `ReplyFact`, `rank`, `WINDOW_DAYS` from Task 1.
- Produces:
  - `cursor.encode_feed_cursor(as_of: datetime, offset: int) -> str`, `cursor.decode_feed_cursor(s: str) -> Tuple[datetime, int]` (raises `ValueError` on garbage, naive datetime or negative offset).
  - `feed_query.aware(dt) -> datetime`, `feed_query.root_ids_of(db, post_ids) -> Dict[int, int]`, `feed_query.ranked_page(db, viewer_id: int, class_ids: List[int], as_of: datetime, offset: int, limit: int) -> Tuple[List[int], bool]`.
  - `/api/feed` response: `{"items", "pinned", "next_cursor", "as_of"}` (`as_of` ISO string with offset).

- [ ] **Step 1: Write the failing tests**

Replace `test_feed_orders_by_activity_and_paginates` in `backend/tests/test_feed.py` with:

```python
def test_feed_paginates_with_a_frozen_cursor(client, db, auth_headers, enrolled, klass, student):
    ids = [_mk(db, student, klass, f"p{i}").id for i in range(5)]
    res = client.get("/api/feed?limit=3", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 3
    assert body["next_cursor"] is not None
    assert body["as_of"]

    res2 = client.get(f"/api/feed?limit=3&cursor={body['next_cursor']}", headers=auth_headers)
    ids2 = [p["id"] for p in res2.json()["items"]]
    assert set(ids2).isdisjoint({p["id"] for p in body["items"]})
    assert {p["id"] for p in body["items"]} | set(ids2) == set(ids)
    assert res2.json()["next_cursor"] is None
```

Create `backend/tests/test_feed_ranking_api.py`:

```python
from datetime import timedelta

from app.models import Like, Post, utcnow


def _mk(db, author, klass, content, age_h=0, **kw):
    p = Post(author_id=author.id, content=content, class_id=klass.id,
             created_at=utcnow() - timedelta(hours=age_h),
             last_activity_at=utcnow() - timedelta(hours=age_h), **kw)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _ids(client, headers, url="/api/feed?limit=50"):
    return [p["id"] for p in client.get(url, headers=headers).json()["items"]]


def test_what_i_gave_aura_sinks_for_me(client, db, auth_headers, enrolled, klass, student, student2):
    a = _mk(db, student2, klass, "a", age_h=1)
    b = _mk(db, student2, klass, "b", age_h=2)
    assert _ids(client, auth_headers)[:2] == [a.id, b.id]
    db.add(Like(user_id=student.id, post_id=a.id))
    db.commit()
    assert _ids(client, auth_headers)[:2] == [b.id, a.id]


def test_it_does_not_sink_for_someone_else(client, db, auth_headers, student2_headers,
                                           enrolled, klass, student, student2, teacher):
    a = _mk(db, teacher, klass, "a", age_h=1)
    b = _mk(db, teacher, klass, "b", age_h=2)
    db.add(Like(user_id=student.id, post_id=a.id))
    db.commit()
    assert _ids(client, student2_headers)[:2] == [a.id, b.id]


def test_a_reply_to_my_post_brings_it_back(client, db, auth_headers, enrolled, klass, student, student2):
    mine = _mk(db, student, klass, "mine", age_h=48)
    fresh = _mk(db, student2, klass, "fresh", age_h=0)
    _mk(db, student2, klass, "answer", age_h=0, parent_id=mine.id)
    assert _ids(client, auth_headers)[:2] == [mine.id, fresh.id]


def test_old_posts_without_recent_replies_go_last_in_date_order(
        client, db, auth_headers, enrolled, klass, student, student2):
    old1 = _mk(db, student2, klass, "old1", age_h=24 * 20)
    old2 = _mk(db, student2, klass, "old2", age_h=24 * 30)
    new = _mk(db, student2, klass, "new", age_h=1)
    revived = _mk(db, student2, klass, "revived", age_h=24 * 40)
    _mk(db, student, klass, "r", age_h=1, parent_id=revived.id)
    ids = _ids(client, auth_headers)
    assert set(ids[:2]) == {new.id, revived.id}
    assert ids[2:] == [old1.id, old2.id]


def test_paging_is_stable_while_i_interact(client, db, auth_headers, enrolled, klass, student, student2):
    all_ids = {_mk(db, student2, klass, f"p{i}", age_h=i).id for i in range(25)}
    seen = []
    url = "/api/feed?limit=10"
    while url:
        body = client.get(url, headers=auth_headers).json()
        page = [p["id"] for p in body["items"]]
        seen += page
        # Between pages: aura on everything just seen, and a brand-new post.
        for pid in page:
            db.add(Like(user_id=student.id, post_id=pid))
        _mk(db, student2, klass, "late")
        url = f"/api/feed?limit=10&cursor={body['next_cursor']}" if body["next_cursor"] else None
    assert len(seen) == len(set(seen))
    assert set(seen) == all_ids


def test_vetoed_roots_stay_and_deleted_ones_do_not(client, db, auth_headers, enrolled, klass, student2):
    v = _mk(db, student2, klass, "v", status="vetoed")
    d = _mk(db, student2, klass, "d", status="deleted")
    ids = _ids(client, auth_headers)
    assert v.id in ids and d.id not in ids


def test_negative_offset_cursor_is_rejected(client, auth_headers):
    from app.services.cursor import encode_feed_cursor
    bad = encode_feed_cursor(utcnow(), -1)
    assert client.get(f"/api/feed?cursor={bad}", headers=auth_headers).status_code == 422
```

The existing `test_feed_scoping.py`, `test_feed_pinned.py` and `test_feed_bad_cursor` must keep passing unchanged.

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && pytest tests/test_feed.py tests/test_feed_ranking_api.py -q`
Expected: FAIL (`as_of` missing, ordering by `last_activity_at`, `encode_feed_cursor` missing)

- [ ] **Step 3: Implement the cursor** (append to `backend/app/services/cursor.py`)

```python
def encode_feed_cursor(as_of: datetime, offset: int) -> str:
    """The feed's cursor: the moment the ranking was frozen and how far in.
    Every page of one load re-ranks with the same as_of, so nothing moves."""
    raw = f"{as_of.isoformat()}|{offset}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_feed_cursor(s: str) -> Tuple[datetime, int]:
    raw = base64.urlsafe_b64decode(s.encode()).decode()
    ts, _, off = raw.rpartition("|")
    as_of = datetime.fromisoformat(ts)
    offset = int(off)
    if as_of.tzinfo is None or offset < 0:
        raise ValueError("bad feed cursor")
    return as_of, offset
```

- [ ] **Step 4: Implement `feed_query.py`**

```python
# backend/app/services/feed_query.py
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
```

- [ ] **Step 5: Rewrite `get_feed`** in `backend/app/routers/posts.py`

Replace the import `from app.services.cursor import decode_cursor, encode_cursor` with `from app.services.cursor import decode_feed_cursor, encode_feed_cursor` (check with `grep -n "encode_cursor\|decode_cursor" backend/app/routers/posts.py` that nothing else in the file uses the old pair; if something does, import both pairs). Add `from app.services.feed_query import ranked_page`. Then:

```python
@feed_router.get("")
def get_feed(
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Ranked per viewer (Bloque 4). The order is frozen at as_of for every
    # page of one load: aura given while scrolling moves nothing until the
    # next refresh. Vetoed posts stay in the feed (they keep their text and
    # carry a veto_reason only the author and teacher see); deleted ones don't.
    if cursor:
        try:
            as_of, offset = decode_feed_cursor(cursor)
        except Exception:
            raise HTTPException(status_code=422, detail="Cursor inválido")
    else:
        as_of, offset = utcnow(), 0
    my_class_ids = viewer_class_ids(db, user)
    ids, has_more = ranked_page(db, user.id, my_class_ids, as_of, offset, limit)
    by_id = {p.id: p for p in db.query(Post)
             .options(selectinload(Post.author), selectinload(Post.klass),
                      selectinload(Post.attachments))
             .filter(Post.id.in_(ids)).all()} if ids else {}
    posts = [by_id[i] for i in ids if i in by_id]
    pinned = _pinned_tareas(db, user, my_class_ids)
    liked = _liked_ids(db, user, [p.id for p in posts] + [p.id for p in pinned])
    aura = _teacher_aura_ids(db, [p.id for p in posts] + [p.id for p in pinned])
    return {"items": [serialize_post(p, liked, viewer=user, teacher_aura_ids=aura) for p in posts],
            "pinned": [serialize_post(p, liked, viewer=user, teacher_aura_ids=aura) for p in pinned],
            "next_cursor": encode_feed_cursor(as_of, offset + limit) if has_more else None,
            "as_of": as_of.isoformat()}
```

Remove `or_`/`and_` from the sqlalchemy import only if nothing else in the file uses them (`grep -n "or_(\|and_(" backend/app/routers/posts.py`).

- [ ] **Step 6: Run the feed tests and the whole suite**

Run: `cd backend && pytest tests/test_feed.py tests/test_feed_ranking_api.py tests/test_feed_scoping.py tests/test_feed_pinned.py -q && pytest tests -q`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/feed_query.py backend/app/services/cursor.py backend/app/routers/posts.py backend/tests/test_feed.py backend/tests/test_feed_ranking_api.py
git commit -m "feat(feed): rank per viewer, page over a frozen as_of"
```

---

### Task 4: `featured_reply` on every feed item

**Files:**
- Modify: `backend/app/schemas.py` (`PostOut`, ~line 223)
- Modify: `backend/app/routers/posts.py` (`get_feed`, new helper `_featured_replies`)
- Test: `backend/tests/test_feed_featured.py`

**Interfaces:**
- Consumes: `ReplyOption`, `pick_featured` (Task 2); `get_feed` from Task 3; existing `_teacher_aura_ids`, `_liked_ids`, `serialize_post`.
- Produces: `PostOut.featured_reply: Optional[PostOut] = None` — set only on `/api/feed` items; every other endpoint leaves it `None`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_feed_featured.py
from datetime import timedelta

from app.models import Like, Post, utcnow


def _mk(db, author, klass, content, age_h=0, **kw):
    p = Post(author_id=author.id, content=content, class_id=klass.id,
             created_at=utcnow() - timedelta(hours=age_h), **kw)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _item(client, headers, pid):
    items = client.get("/api/feed?limit=50", headers=headers).json()["items"]
    return next(p for p in items if p["id"] == pid)


def test_no_replies_no_featured(client, db, auth_headers, enrolled, klass, student):
    root = _mk(db, student, klass, "root")
    assert _item(client, auth_headers, root.id)["featured_reply"] is None


def test_the_teacher_aura_reply_is_featured(client, db, auth_headers, enrolled, klass,
                                            student, student2, teacher):
    root = _mk(db, student, klass, "root")
    popular = _mk(db, student2, klass, "popular", parent_id=root.id, like_count=5)
    blessed = _mk(db, student2, klass, "blessed", parent_id=root.id, age_h=2)
    db.add(Like(user_id=teacher.id, post_id=blessed.id))
    db.commit()
    fr = _item(client, auth_headers, root.id)["featured_reply"]
    assert fr["id"] == blessed.id
    assert fr["teacher_aura"] is True
    assert fr["author"]["id"] == student2.id
    assert popular.id != fr["id"]


def test_most_aura_then_most_recent(client, db, auth_headers, enrolled, klass, student, student2):
    root = _mk(db, student, klass, "root")
    _mk(db, student2, klass, "older", parent_id=root.id, age_h=3, like_count=2)
    newer = _mk(db, student2, klass, "newer", parent_id=root.id, age_h=1, like_count=2)
    assert _item(client, auth_headers, root.id)["featured_reply"]["id"] == newer.id


def test_level3_and_inactive_replies_are_never_featured(client, db, auth_headers, enrolled,
                                                        klass, student, student2):
    root = _mk(db, student, klass, "root")
    l2 = _mk(db, student2, klass, "l2", parent_id=root.id, status="deleted")
    _mk(db, student2, klass, "l3", parent_id=l2.id, like_count=9)
    _mk(db, student2, klass, "vetoed", parent_id=root.id, status="vetoed", like_count=9)
    assert _item(client, auth_headers, root.id)["featured_reply"] is None


def test_never_under_a_tarea(client, db, auth_headers, enrolled, klass, student, teacher):
    tarea = _mk(db, teacher, klass, "tarea", type="tarea")
    _mk(db, student, klass, "mi respuesta", parent_id=tarea.id, like_count=3)
    assert _item(client, auth_headers, tarea.id)["featured_reply"] is None


def test_never_under_an_examen(client, db, auth_headers, enrolled, klass, student, teacher):
    examen = _mk(db, teacher, klass, "examen", type="examen")
    _mk(db, student, klass, "mi respuesta", parent_id=examen.id)
    assert _item(client, auth_headers, examen.id)["featured_reply"] is None


def test_the_thread_endpoint_carries_no_featured_reply(client, db, auth_headers, enrolled,
                                                       klass, student, student2):
    root = _mk(db, student, klass, "root")
    _mk(db, student2, klass, "r", parent_id=root.id)
    body = client.get(f"/api/posts/{root.id}", headers=auth_headers).json()
    assert body["post"]["featured_reply"] is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && pytest tests/test_feed_featured.py -q`
Expected: FAIL (`KeyError: 'featured_reply'`)

- [ ] **Step 3: Add the field** to `PostOut` in `backend/app/schemas.py`, after `parent_id`:

```python
    # Only on /api/feed items: the one comment shown under the card.
    featured_reply: Optional["PostOut"] = None
```

- [ ] **Step 4: Add the helper and wire it into `get_feed`** (`backend/app/routers/posts.py`; import `ReplyOption, pick_featured` from `app.services.feed_rank` and `aware` from `app.services.feed_query`)

```python
# A tarea's or examen's replies may be homework answers — the profile hides
# them, so the feed never puts one under a card either.
FEATURED_ROOT_TYPES = ("regular", "participacion")


def _featured_replies(db: Session, roots: List[Post]) -> dict:
    """root id → the reply shown under its card (level 2, active only)."""
    eligible = [p.id for p in roots if p.type in FEATURED_ROOT_TYPES]
    if not eligible:
        return {}
    replies = (db.query(Post)
               .options(selectinload(Post.author), selectinload(Post.klass),
                        selectinload(Post.attachments))
               .filter(Post.parent_id.in_(eligible), Post.status == "active").all())
    blessed = _teacher_aura_ids(db, [r.id for r in replies])
    by_root: dict = {}
    for r in replies:
        by_root.setdefault(r.parent_id, []).append(r)
    out = {}
    for root_id, group in by_root.items():
        pick = pick_featured([ReplyOption(r.id, aware(r.created_at), r.like_count, r.id in blessed)
                              for r in group])
        out[root_id] = next(r for r in group if r.id == pick)
    return out
```

In `get_feed`, after computing `pinned`, replace the `liked`/`aura`/return lines with:

```python
    featured = _featured_replies(db, posts)
    every = [p.id for p in posts] + [p.id for p in pinned] + [r.id for r in featured.values()]
    liked = _liked_ids(db, user, every)
    aura = _teacher_aura_ids(db, every)

    def out(p: Post):
        o = serialize_post(p, liked, viewer=user, teacher_aura_ids=aura)
        if p.id in featured:
            o.featured_reply = serialize_post(featured[p.id], liked, viewer=user,
                                              teacher_aura_ids=aura)
        return o

    return {"items": [out(p) for p in posts],
            "pinned": [serialize_post(p, liked, viewer=user, teacher_aura_ids=aura) for p in pinned],
            "next_cursor": encode_feed_cursor(as_of, offset + limit) if has_more else None,
            "as_of": as_of.isoformat()}
```

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_feed_featured.py -q && pytest tests -q`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/posts.py backend/tests/test_feed_featured.py
git commit -m "feat(feed): one featured comment under each card"
```

---

### Task 5: `GET /api/feed/has-new`

**Files:**
- Modify: `backend/app/services/feed_query.py` (add `has_new`)
- Modify: `backend/app/routers/posts.py` (new route on `feed_router`)
- Test: `backend/tests/test_feed_has_new.py`

**Interfaces:**
- Consumes: `root_ids_of` (Task 3), `assignment_visible`, `viewer_class_ids`.
- Produces: `feed_query.has_new(db, viewer_id: int, class_ids: List[int], since: datetime) -> bool`; `GET /api/feed/has-new?since=<iso>` → `{"has_new": bool}`; 422 on naive or unparseable `since`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_feed_has_new.py
from datetime import date
from urllib.parse import quote

from app.models import Class, Post


def _since(client, headers):
    return client.get("/api/feed", headers=headers).json()["as_of"]


def _has_new(client, headers, since):
    res = client.get(f"/api/feed/has-new?since={quote(since)}", headers=headers)
    assert res.status_code == 200
    return res.json()["has_new"]


def _post(db, author, klass, **kw):
    p = Post(author_id=author.id, class_id=klass.id, content="x", **kw)
    db.add(p)
    db.commit()
    return p


def test_nothing_new_right_after_loading(client, auth_headers, enrolled):
    since = _since(client, auth_headers)
    assert _has_new(client, auth_headers, since) is False


def test_someone_elses_post_is_new(client, db, auth_headers, enrolled, klass, student2):
    since = _since(client, auth_headers)
    _post(db, student2, klass)
    assert _has_new(client, auth_headers, since) is True


def test_my_own_post_is_not_new(client, db, auth_headers, enrolled, klass, student):
    since = _since(client, auth_headers)
    _post(db, student, klass)
    assert _has_new(client, auth_headers, since) is False


def test_another_class_tarea_is_not_new(client, db, auth_headers, enrolled, teacher):
    other = Class(name="Otra", code="OTRA2026TEST", teacher_id=teacher.id,
                  start_date=date(2026, 8, 17), end_date=date(2026, 12, 4), schedule_json=[])
    db.add(other)
    db.commit()
    since = _since(client, auth_headers)
    _post(db, teacher, other, type="tarea")
    assert _has_new(client, auth_headers, since) is False


def test_a_reply_in_my_thread_is_new(client, db, auth_headers, enrolled, klass, student, student2):
    root = _post(db, student2, klass)
    _post(db, student, klass, parent_id=root.id)
    since = _since(client, auth_headers)
    _post(db, student2, klass, parent_id=root.id)
    assert _has_new(client, auth_headers, since) is True


def test_a_reply_to_my_comment_at_level3_is_new(client, db, auth_headers, enrolled, klass,
                                                student, student2):
    root = _post(db, student2, klass)
    mine = _post(db, student, klass, parent_id=root.id)
    since = _since(client, auth_headers)
    _post(db, student2, klass, parent_id=mine.id)
    assert _has_new(client, auth_headers, since) is True


def test_a_reply_in_an_unrelated_thread_is_not_new(client, db, auth_headers, enrolled, klass,
                                                   student2, teacher):
    root = _post(db, teacher, klass)
    since = _since(client, auth_headers)
    _post(db, student2, klass, parent_id=root.id)
    assert _has_new(client, auth_headers, since) is False


def test_naive_or_garbage_since_is_rejected(client, auth_headers):
    assert client.get("/api/feed/has-new?since=2026-10-21T10:00:00",
                      headers=auth_headers).status_code == 422
    assert client.get("/api/feed/has-new?since=ayer", headers=auth_headers).status_code == 422
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && pytest tests/test_feed_has_new.py -q`
Expected: FAIL (404 on `/api/feed/has-new`)

- [ ] **Step 3: Implement `has_new`** (append to `feed_query.py`)

```python
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
    if not threads:
        return False
    level2 = {pid for (pid,) in db.query(Post.id).filter(Post.parent_id.in_(threads))}
    replies = (db.query(Post.id)
               .filter(Post.parent_id.in_(threads | level2), Post.created_at > since,
                       Post.author_id != viewer_id, Post.status == "active"))
    return bool(db.query(replies.exists()).scalar())
```

- [ ] **Step 4: Add the route** in `backend/app/routers/posts.py`, **above** `get_feed` is fine (distinct path); import `has_new` from `app.services.feed_query`:

```python
@feed_router.get("/has-new")
def feed_has_new(since: str = Query(...), user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    try:
        when = datetime.fromisoformat(since)
    except ValueError:
        raise HTTPException(status_code=422, detail="Fecha inválida")
    if when.tzinfo is None:
        raise HTTPException(status_code=422, detail="Fecha inválida")
    return {"has_new": has_new(db, user.id, viewer_class_ids(db, user), when)}
```

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_feed_has_new.py -q && pytest tests -q`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/feed_query.py backend/app/routers/posts.py backend/tests/test_feed_has_new.py
git commit -m "feat(feed): has-new endpoint for the new-posts pill"
```

---

### Task 6: Client — the feed only moves when asked

**Files:**
- Modify: `frontend/src/lib/types.ts` (`Post.featured_reply`, `FeedPage.as_of`)
- Modify: `frontend/src/lib/feed.ts` (`firstPageOnly`, `refreshFeed`)
- Modify: `frontend/src/lib/postCache.ts` (`patchFeedPost`, `dropFromFeed`)
- Modify: `frontend/src/pages/Home.tsx` (query options)
- Modify: `frontend/src/pages/Compose.tsx:62`, `frontend/src/pages/Thread.tsx:56,65`, `frontend/src/pages/Revisar.tsx:273,285,306`, `frontend/src/components/RemovePhotoButton.tsx:31`
- Test: `frontend/src/lib/feed.test.ts`, `frontend/src/lib/postCache.test.ts` (append)

**Interfaces:**
- Produces:
  - `firstPageOnly(d: InfiniteData<FeedPage> | undefined): InfiniteData<FeedPage> | undefined`
  - `refreshFeed(qc: QueryClient): Promise<void>` — the only way the feed refetches.
  - `patchFeedPost(qc: QueryClient, id: number, fn: (p: Post) => Post): void`
  - `dropFromFeed(qc: QueryClient, id: number): void`
  - `Post.featured_reply?: Post | null`, `FeedPage.as_of: string`

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/lib/feed.test.ts` (reuse its `post` helper):

```ts
import { QueryClient, type InfiniteData } from "@tanstack/react-query";
import { firstPageOnly, refreshFeed } from "./feed";

const page = (ids: number[], cursor: string | null): FeedPage => ({
  items: ids.map(post),
  pinned: [],
  next_cursor: cursor,
  as_of: "2026-10-21T12:00:00+00:00",
});

describe("firstPageOnly", () => {
  it("keeps only page 1 so a refetch never mixes a new as_of with old cursors", () => {
    const d: InfiniteData<FeedPage, string | null> = {
      pages: [page([1, 2], "c1"), page([3], null)],
      pageParams: [null, "c1"],
    };
    const out = firstPageOnly(d)!;
    expect(out.pages).toHaveLength(1);
    expect(out.pageParams).toEqual([null]);
  });

  it("leaves an empty cache alone", () => {
    expect(firstPageOnly(undefined)).toBeUndefined();
  });
});

describe("refreshFeed", () => {
  it("truncates and marks the feed stale", async () => {
    const qc = new QueryClient();
    qc.setQueryData(["feed"], {
      pages: [page([1], "c1"), page([2], null)],
      pageParams: [null, "c1"],
    });
    await refreshFeed(qc);
    const d = qc.getQueryData<InfiniteData<FeedPage>>(["feed"])!;
    expect(d.pages).toHaveLength(1);
    expect(qc.getQueryState(["feed"])!.isInvalidated).toBe(true);
  });
});
```

Append to `frontend/src/lib/postCache.test.ts` (reuse or copy the file's existing `Post` fixture helper; if it has none, copy the `post` helper from `feed.test.ts`):

```ts
import { QueryClient, type InfiniteData } from "@tanstack/react-query";
import { dropFromFeed, patchFeedPost } from "./postCache";

function seeded() {
  const qc = new QueryClient();
  qc.setQueryData(["feed"], {
    pages: [{ items: [post(1), post(2)], pinned: [post(2)], next_cursor: null, as_of: "x" }],
    pageParams: [null],
  });
  return qc;
}

describe("patchFeedPost", () => {
  it("patches the post in items and pinned without refetching", () => {
    const qc = seeded();
    patchFeedPost(qc, 2, (p) => ({ ...p, reply_count: p.reply_count + 1 }));
    const d = qc.getQueryData<InfiniteData<FeedPage>>(["feed"])!;
    expect(d.pages[0].items[1].reply_count).toBe(1);
    expect(d.pages[0].pinned[0].reply_count).toBe(1);
    expect(qc.getQueryState(["feed"])!.isInvalidated).toBe(false);
  });
});

describe("dropFromFeed", () => {
  it("removes a deleted root from items and pinned", () => {
    const qc = seeded();
    dropFromFeed(qc, 2);
    const d = qc.getQueryData<InfiniteData<FeedPage>>(["feed"])!;
    expect(d.pages[0].items.map((p) => p.id)).toEqual([1]);
    expect(d.pages[0].pinned).toEqual([]);
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend && npm test -- src/lib/feed.test.ts src/lib/postCache.test.ts`
Expected: FAIL (missing exports)

- [ ] **Step 3: Types** — in `frontend/src/lib/types.ts` add to `Post` (after `veto_reason`):

```ts
  /** Feed only: the one comment shown under the card. */
  featured_reply?: Post | null;
```

and to `FeedPage` (after `next_cursor`):

```ts
  /** When this load's ranking was frozen. Every page of one load shares it;
   *  it is also the `since` for the new-posts check. */
  as_of: string;
```

- [ ] **Step 4: `feed.ts`**

```ts
import type { InfiniteData, QueryClient } from "@tanstack/react-query";

/** Page 1 only. Refetching every stored page would pair a fresh first page
 *  (new as_of) with cursors frozen at the old one. */
export function firstPageOnly(
  d: InfiniteData<FeedPage> | undefined,
): InfiniteData<FeedPage> | undefined {
  if (!d) return d;
  return { pages: d.pages.slice(0, 1), pageParams: d.pageParams.slice(0, 1) };
}

/** The only way the feed reorders (Bloque 4): publishing, tapping Inicio
 *  on Inicio, and the new-posts pill. Everything else patches the cache. */
export function refreshFeed(qc: QueryClient): Promise<void> {
  qc.setQueryData<InfiniteData<FeedPage>>(["feed"], firstPageOnly);
  return qc.invalidateQueries({ queryKey: ["feed"], exact: true });
}
```

(Merge the `FeedPage`/`Post` type import with the existing one at the top of the file.)

- [ ] **Step 5: `postCache.ts`** (append)

```ts
/** For screens that know a post's id but not the Post (the review queue,
 *  a thread's root). Patches; never refetches — a refetch reorders. */
export function patchFeedPost(qc: QueryClient, id: number, fn: (p: Post) => Post): void {
  qc.setQueryData<InfiniteData<FeedPage>>(["feed"], (d) => mapFeed(d, id, fn));
}

/** A deleted root leaves the feed (the server hides it too). */
export function dropFromFeed(qc: QueryClient, id: number): void {
  qc.setQueryData<InfiniteData<FeedPage>>(["feed"], (d) =>
    d && {
      ...d,
      pages: d.pages.map((pg) => ({
        ...pg,
        items: pg.items.filter((p) => p.id !== id),
        pinned: pg.pinned.filter((p) => p.id !== id),
      })),
    },
  );
}
```

- [ ] **Step 6: Home query options** — in `frontend/src/pages/Home.tsx` add to the `useInfiniteQuery` options:

```ts
    // Never refetch on its own: a refetch reorders under the reader's thumb.
    // refreshFeed() is the only way in (Bloque 4).
    staleTime: Infinity,
    refetchOnWindowFocus: false,
```

- [ ] **Step 7: Replace every other feed invalidation**

`Compose.tsx` onSuccess: replace `void qc.invalidateQueries({ queryKey: ["feed"] });` with `void refreshFeed(qc);` (import from `@/lib/feed`).

`Thread.tsx` reply onSuccess: replace the feed invalidation with
```ts
      // The thread's root gains a reply; patch it rather than reorder the feed.
      patchFeedPost(qc, Number(id), (p) => ({ ...p, reply_count: p.reply_count + 1 }));
```
`Thread.tsx` remove onSuccess: replace the feed invalidation with
```ts
      if (post.id === Number(id)) dropFromFeed(qc, post.id);
      else patchFeedPost(qc, Number(id), (p) => ({ ...p, reply_count: Math.max(0, p.reply_count - 1) }));
```
(keep the existing navigate / thread invalidation lines after it).

`Revisar.tsx`:
- `review` mutation: in `onSettled` drop the `["feed"]` invalidation; add an `onSuccess: (_d, { postId, reviewed }) => patchFeedPost(qc, postId, (p) => teacherAura(p, reviewed))`.
- `bulk` mutation: drop the `["feed"]` invalidation; add `onSuccess: (_d, ids) => ids.forEach((id) => patchFeedPost(qc, id, (p) => teacherAura(p, true)))`.
- `toggle` (veto) mutation: drop the `["feed"]` invalidation; add `onSuccess: (_d, { postId, vetoed }) => patchFeedPost(qc, postId, (p) => ({ ...p, status: vetoed ? "vetoed" : "active" }))`.
- Add, in `postCache.ts` next to `toggleAura`, and import it in `Revisar.tsx`:

```ts
/** Validating is the teacher's aura (Bloque 2): set it on or off, idempotently. */
export function teacherAura(p: Post, on: boolean): Post {
  if (p.liked_by_me === on) return { ...p, teacher_aura: on };
  return { ...p, liked_by_me: on, teacher_aura: on, like_count: Math.max(0, p.like_count + (on ? 1 : -1)) };
}
```

`RemovePhotoButton.tsx`: remove `["feed"]` from the invalidation list and add `void refreshFeed(qc);` after the loop (the teacher is on a profile, not the feed, so a reorder costs nothing; the old avatar must not linger).

Verify: `grep -rn 'queryKey: \["feed"\]' frontend/src` returns only `Home.tsx` and `feed.ts`.

- [ ] **Step 8: Run checks**

Run: `cd frontend && npm run lint && npm run typecheck && npm test`
Expected: all PASS

- [ ] **Step 9: Commit**

```bash
git add frontend/src
git commit -m "feat(feed): the feed only reorders when you ask"
```

---

### Task 7: Client — "Publicaciones nuevas" pill and Inicio-on-Inicio

**Files:**
- Modify: `frontend/src/pages/Home.tsx`
- Modify: `frontend/src/components/Shell.tsx` (home link)
- Modify: `frontend/src/strings/es.ts` (`feed.newPosts`)

**Interfaces:**
- Consumes: `refreshFeed` (Task 6), `FeedPage.as_of`, `GET /api/feed/has-new` (Task 5).

- [ ] **Step 1: Copy placeholder** — in `es.ts` under `feed`, add:

```ts
    newPosts: "Publicaciones nuevas",
```

- [ ] **Step 2: The pill in `Home.tsx`**

Imports: `useState` with the existing React import, `useQueryClient` from `@tanstack/react-query`, `refreshFeed` from `@/lib/feed`, `Button` from `@/components/ui/button`, `RiArrowUpLine` from `@remixicon/react`.

Inside `Home`, after the query:

```tsx
  const qc = useQueryClient();
  const [hasNew, setHasNew] = useState(false);
  const asOf = q.data?.pages[0]?.as_of;

  // Coming back never reorders (Mario, 2026-10-21): ask whether something
  // new exists and offer it instead.
  useEffect(() => {
    if (!asOf) return;
    setHasNew(false);
    const check = () => {
      if (document.visibilityState !== "visible") return;
      api<{ has_new: boolean }>(`/api/feed/has-new?since=${encodeURIComponent(asOf)}`)
        .then((r) => setHasNew(r.has_new))
        .catch(() => {});
    };
    check();
    document.addEventListener("visibilitychange", check);
    return () => document.removeEventListener("visibilitychange", check);
  }, [asOf]);

  function showNew() {
    setHasNew(false);
    window.scrollTo({ top: 0 });
    void refreshFeed(qc);
  }
```

In the returned JSX, as the first child of the outer `<div className="divide-y">` (before `{veto.dialog}`):

```tsx
      {hasNew && (
        <div className="pointer-events-none sticky top-14 z-10 flex justify-center border-none py-2">
          <Button size="sm" className="pointer-events-auto shadow-md" onClick={showNew}>
            <RiArrowUpLine data-icon="inline-start" />
            {es.feed.newPosts}
          </Button>
        </div>
      )}
```

If ESLint's `react-hooks/set-state-in-effect` flags the `setHasNew(false)` inside the effect, drop that line and instead key the state on the load: `const [newFor, setNewFor] = useState<string | null>(null); const hasNew = newFor === asOf;` with `.then((r) => r.has_new && setNewFor(asOf))` and `setNewFor(null)` in `showNew`. `top-14` assumes the 56 px header; match the header's real height if it differs.

- [ ] **Step 3: Inicio while on Inicio** — in `Shell.tsx`, import `useLocation`, `useQueryClient`, `refreshFeed`; then:

```tsx
  const location = useLocation();
  const qc = useQueryClient();
```

and on the home `<Link to="/" …>` add:

```tsx
          onClick={(e) => {
            // Already on Inicio: the tap means "show me what's new".
            if (location.pathname === "/") {
              e.preventDefault();
              window.scrollTo({ top: 0 });
              void refreshFeed(qc);
            }
          }}
```

- [ ] **Step 4: Run checks**

Run: `cd frontend && npm run lint && npm run typecheck && npm test`
Expected: all PASS

- [ ] **Step 5: Manual check on a phone viewport** (390×844): run backend (`cd backend && uvicorn app.main:app --reload`) and frontend (`cd frontend && npm run dev`); load the feed, post from a second account, switch tabs and come back → pill appears, order unchanged; tap pill → scrolls up, new post first. Tap Inicio on Inicio → reloads at top. Open a thread, reply, go back → same order and scroll position.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat(feed): new-posts pill; Inicio on Inicio refreshes"
```

---

### Task 8: Client — the featured comment under the card

**Files:**
- Create: `frontend/src/components/FeaturedReply.tsx`
- Modify: `frontend/src/pages/Home.tsx` (render it under each item)
- Modify: `frontend/src/strings/es.ts` (`feed.seeAllReplies`)

**Interfaces:**
- Consumes: `Post.featured_reply` (Task 6 types), `UserLink`.
- Produces: `<FeaturedReply reply={Post} rootId={number} replyCount={number} />`.

- [ ] **Step 1: Copy placeholder** — in `es.ts` under `feed`:

```ts
    seeAllReplies: "Ver las {n} respuestas",
```

- [ ] **Step 2: Component**

```tsx
// frontend/src/components/FeaturedReply.tsx
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
  return (
    <div className="ml-14 mr-4 mb-3 border-l-2 pl-3 text-sm">
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
```

- [ ] **Step 3: Render in `Home.tsx`** — replace the items `.map` with:

```tsx
      {posts.filter((p) => !pinnedIds.has(p.id)).map((p) => (
        <div key={p.id}>
          <PostCard post={p} onLike={(post) => like.mutate(post)} onVeto={onVeto} />
          {p.featured_reply && p.status !== "deleted" && (
            <FeaturedReply reply={p.featured_reply} rootId={p.id} replyCount={p.reply_count} />
          )}
        </div>
      ))}
```

- [ ] **Step 4: Run checks**

Run: `cd frontend && npm run lint && npm run typecheck && npm test`
Expected: all PASS

- [ ] **Step 5: Manual check on a phone viewport** (390×844): a post with replies shows one comment, indented under the text column, two lines max; the name opens the profile; the text and "Ver las N respuestas" open the thread; a tarea never shows one.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat(feed): featured comment under each card"
```

---

### Task 9: Metrics script and planning docs

**Files:**
- Create: `backend/scripts/feed_metrics.py`
- Test: `backend/tests/test_feed_metrics.py`
- Modify: `planning/roadmap.md` (Bloque 4 checkboxes), `planning/changelog.md` (new entry, Spanish)

**Interfaces:**
- Produces: `weekly_metrics(rows: Iterable[Tuple[int, int, Optional[int], datetime]]) -> List[Tuple[str, float, float]]` — input rows are `(post_id, author_id, root_id_or_None, created_at)` for non-deleted posts; output rows are `(iso_week "2026-W43", replies_per_active_student, share_of_roots_with_a_reply)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_feed_metrics.py
from datetime import datetime, timezone

from scripts.feed_metrics import weekly_metrics


def d(day):
    return datetime(2026, 10, day, 12, tzinfo=timezone.utc)


def test_weekly_metrics():
    # (post_id, author_id, root_id or None for a root, created_at) — week 2026-W43
    rows = [
        (10, 1, None, d(19)),   # root
        (11, 2, None, d(20)),   # root, never answered
        (12, 3, 10, d(20)),     # replies to 10
        (13, 3, 10, d(21)),
        (14, 1, 10, d(22)),
    ]
    # active: 1, 2, 3 → 3 replies / 3 = 1.0; roots answered: 1 of 2 = 0.5
    assert weekly_metrics(rows) == [("2026-W43", 1.0, 0.5)]


def test_empty():
    assert weekly_metrics([]) == []
```

A root counts as answered (in the week it was created) if any reply to it exists at all.

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/test_feed_metrics.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'scripts'`)

- [ ] **Step 3: Implement**

```python
# backend/scripts/feed_metrics.py
"""Before/after numbers for the feed ranking (Bloque 4).

Run before a weights change and again two or three weeks later:
    cd backend && python -m scripts.feed_metrics
Reads existing tables only. Teachers are counted like anyone else; the
numbers are for comparing weeks, not for grading.
"""
from collections import defaultdict
from datetime import datetime
from typing import Iterable, List, Optional, Tuple


def _week(dt: datetime) -> str:
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def weekly_metrics(rows: Iterable[Tuple[int, int, Optional[int], datetime]]
                   ) -> List[Tuple[str, float, float]]:
    rows = list(rows)
    answered = {root for _, _, root, _ in rows if root is not None}
    active = defaultdict(set)
    replies = defaultdict(int)
    roots = defaultdict(int)
    roots_answered = defaultdict(int)
    for pid, author, root, at in rows:
        wk = _week(at)
        active[wk].add(author)
        if root is None:
            roots[wk] += 1
            roots_answered[wk] += pid in answered
        else:
            replies[wk] += 1
    out = []
    for wk in sorted(active):
        rps = round(replies[wk] / len(active[wk]), 2)
        share = round(roots_answered[wk] / roots[wk], 2) if roots[wk] else 0.0
        out.append((wk, rps, share))
    return out


def main() -> None:
    from app.database import SessionLocal
    from app.models import Post
    from app.services.feed_query import root_ids_of

    db = SessionLocal()
    try:
        posts = db.query(Post.id, Post.author_id, Post.parent_id, Post.created_at).filter(
            Post.status != "deleted").all()
        root_of = root_ids_of(db, [p.id for p in posts if p.parent_id is not None])
        rows = [(p.id, p.author_id, root_of.get(p.id) if p.parent_id else None, p.created_at)
                for p in posts]
    finally:
        db.close()
    print("semana      respuestas/alumno  posts con respuesta")
    for wk, rps, share in weekly_metrics(rows):
        print(f"{wk}   {rps:>17.2f}  {share:>18.0%}")


if __name__ == "__main__":
    main()
```

Also create an empty `backend/scripts/__init__.py` so `python -m scripts.feed_metrics` and the test import work from `backend/`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && pytest tests/test_feed_metrics.py -q && pytest tests -q`
Expected: all PASS. Also run `cd backend && python -m scripts.feed_metrics` against the local DB — it prints a table (possibly empty) without error.

- [ ] **Step 5: Planning docs** — in `planning/roadmap.md`, Bloque 4: mark "Spec primero" `[x]`, "Implementación + tests" `[x]`, "Promover los comentarios" `[x]` (both sub-bullets), each with `✅ <date>`; update the "Empieza aquí" state line to say Bloque 4 is in production and that the next step is to run `python -m scripts.feed_metrics` two or three weeks after deploying, then decide weights / question 7 in `future.md`. Add a dated entry to `planning/changelog.md` in Spanish, matching the existing entries' style, summarizing: el feed se ordena por persona; lo que tocaste baja; una respuesta te lo regresa; el orden sólo cambia al refrescar; píldora "Publicaciones nuevas"; un comentario destacado bajo cada post (nunca en tareas ni exámenes).

- [ ] **Step 6: Commit**

```bash
git add backend/scripts backend/tests/test_feed_metrics.py planning/roadmap.md planning/changelog.md
git commit -m "chore(feed): weekly metrics script; roadmap and changelog for Bloque 4"
```
