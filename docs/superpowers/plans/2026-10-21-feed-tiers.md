# Bloque 4b — Feed Tiers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Order the feed in tiers — the teacher's pending work, then untouched posts, then touched posts — so a refresh shows something new and the teacher's feed doubles as their review queue.

**Architecture:** `feed_rank.rank` gains a tier per post (pure). `feed_query.teacher_pending` computes, as of `as_of`, which of the teacher's participaciones/tareas/exámenes need them and since when; `ranked_page` adds those roots to the candidates and passes their `pending_at` to `rank`; `get_feed` sets `pending_count` on tareas/exámenes. The client shows a "N por calificar" badge.

**Tech Stack:** FastAPI, SQLAlchemy, pytest; React, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-21-feed-tiers-design.md` (amends `2026-10-21-feed-ranking-design.md`)

## Global Constraints

- No migration. Python 3.9 (no `X | Y` types).
- Pending means what `/revisar` means, bounded by `as_of`.
- Only a `role == "teacher"` viewer gets tier 1, and only for classes where `Class.teacher_id == viewer.id`.
- Replies under tarea/examen roots never count as touches' lift (unchanged from Bloque 4 — `load_candidates` gives those roots no replies).
- Copy is a placeholder in `es.ts`; every number shown is a count, not points (no `formatPoints`).
- Backend: `cd backend && .venv/bin/python -m pytest tests -q -p no:warnings`. Frontend: `cd frontend && npm run lint && npm run build && npm test`.
- Commit, never push; the controller pushes after the final review.

## Review Focus

1. **Stale review after a resubmission** — a review written against an older entrega must not count as graded (the `counting_review` rule) → test in Task 2.
2. **Grading/validating mid-scroll** — a review or `reviewed_at` after `as_of` must not change pages of the same load → paging test in Task 2.
3. **Ghost/polizón entregas** — only active enrollments count toward pending (as in `/revisar`) → test in Task 2.
4. **Another teacher's class** — never in tier 1 → test in Task 2.
5. **Old pending outside the 14-day window** — still tier 1 → test in Task 2.

---

### Task 1: Tiers in the pure ranking

**Files:**
- Modify: `backend/app/services/feed_rank.py`
- Test: `backend/tests/test_feed_rank.py` (append)

**Interfaces:**
- Produces: `tier(c: Candidate, viewer_id: int, aura_at: Optional[datetime], as_of: datetime, pending_at: Optional[datetime] = None) -> int` (1, 2 or 3); `rank(candidates, viewer_id, aura_at, as_of, pending_at: Optional[Dict[int, datetime]] = None) -> List[int]`. `score` unchanged in value.

- [ ] **Step 1: Write the failing tests** (append)

```python
from app.services.feed_rank import tier  # noqa: E402


def test_untouched_goes_above_touched_whatever_the_age():
    touched = post(1, age=0)
    old = post(2, age=24 * 10)
    assert rank([touched, old], ME, {1: ago(0)}, AS_OF) == [2, 1]


def test_a_reply_to_me_puts_a_touched_post_back_in_tier_2():
    mine = post(1, author=ME, age=48, replies=[reply(ANA, 1, parent_author=ME)])
    assert tier(mine, ME, None, AS_OF) == 2


def test_aura_then_a_reply_to_someone_else_stays_in_tier_3():
    c = post(1, age=10, replies=[reply(LUIS, 1)])
    assert tier(c, ME, ago(5), AS_OF) == 3


def test_pending_is_tier_1_newest_first():
    a = post(1, age=50)
    b = post(2, age=1)
    fresh = post(3, age=0)
    pending = {1: ago(2), 2: ago(30)}
    # pending_at, not age, orders tier 1: post 1 became pending more recently.
    assert rank([a, b, fresh], ME, {}, AS_OF, pending) == [1, 2, 3]


def test_pending_wins_over_touched():
    c = post(1, author=ME, age=0)
    assert tier(c, ME, None, AS_OF, pending_at=ago(1)) == 1


def test_no_pending_map_means_no_tier_1():
    assert rank([post(1), post(2, age=1)], ME, {}, AS_OF) == [1, 2]
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_feed_rank.py -q -p no:warnings`
Expected: FAIL — `ImportError: cannot import name 'tier'`

- [ ] **Step 3: Implement** — refactor `score` into a helper that also reports touched/lift, add `tier`, rewrite `rank`:

```python
def _evaluate(c: Candidate, viewer_id: int, aura_at: Optional[datetime],
              as_of: datetime) -> Tuple[float, bool, float]:
    """(score, touched, lift) — one pass, so tier and score never disagree."""
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
    return base * factor + W_LIFT * log1p(lift), bool(touches), lift


def score(c: Candidate, viewer_id: int, aura_at: Optional[datetime],
          as_of: datetime) -> float:
    return _evaluate(c, viewer_id, aura_at, as_of)[0]


def tier(c: Candidate, viewer_id: int, aura_at: Optional[datetime], as_of: datetime,
         pending_at: Optional[datetime] = None) -> int:
    """1: the teacher's pending work. 2: untouched, or brought back by a reply.
    3: touched — below everything new (Bloque 4b)."""
    if pending_at is not None:
        return 1
    _, touched, lift = _evaluate(c, viewer_id, aura_at, as_of)
    return 3 if touched and lift == 0 else 2


def rank(candidates: Iterable[Candidate], viewer_id: int,
         aura_at: Dict[int, datetime], as_of: datetime,
         pending_at: Optional[Dict[int, datetime]] = None) -> List[int]:
    """Post ids, best first: by tier, then pending_at (tier 1, newest first)
    or score (tiers 2–3). Ties break on post id descending, so the order is
    total and the same on every page of one load."""
    pending_at = pending_at or {}
    keyed = []
    for c in candidates:
        p_at = pending_at.get(c.post_id)
        s, touched, lift = _evaluate(c, viewer_id, aura_at.get(c.post_id), as_of)
        if p_at is not None:
            keyed.append(((1, -p_at.timestamp(), -c.post_id), c.post_id))
        else:
            t = 3 if touched and lift == 0 else 2
            keyed.append(((t, -s, -c.post_id), c.post_id))
    keyed.sort(key=lambda k: k[0])
    return [pid for _, pid in keyed]
```

Update the module docstring's first paragraph to mention tiers.

- [ ] **Step 4: Run to verify** — `cd backend && .venv/bin/python -m pytest tests/test_feed_rank.py -q -p no:warnings` → all PASS (the old tests too: `rank` on untouched posts is unchanged; check `test_a_reply_to_me_brings_my_post_above_a_fresh_one` still holds — both are tier 2).

- [ ] **Step 5: Commit** — `git commit -m "feat(feed): tiers — touched sinks below everything new"`

---

### Task 2: The teacher's pending work in the feed

**Files:**
- Modify: `backend/app/services/feed_query.py` (`teacher_pending`, `ranked_page`)
- Modify: `backend/app/schemas.py` (`PostOut.pending_count`)
- Modify: `backend/app/routers/posts.py` (`get_feed`)
- Test: create `backend/tests/test_feed_tiers.py`

**Interfaces:**
- Consumes: `rank(..., pending_at)` (Task 1).
- Produces: `teacher_pending(db, teacher_id: int, as_of: datetime) -> Dict[int, Tuple[datetime, Optional[int]]]` (root id → (pending_at, count or None for participaciones)); `ranked_page(db, viewer_id, class_ids, as_of, offset, limit, pending_at: Optional[Dict[int, datetime]] = None)`; `PostOut.pending_count: Optional[int] = None`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_feed_tiers.py
from datetime import date, timedelta

from app.models import Attachment, Class, Enrollment, Like, Post, Review, User, utcnow


def _mk(db, author, klass, content="x", age_h=0, **kw):
    p = Post(author_id=author.id, content=content, class_id=klass.id,
             created_at=utcnow() - timedelta(hours=age_h), **kw)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _items(client, headers, url="/api/feed?limit=50"):
    return client.get(url, headers=headers).json()["items"]


def _ids(client, headers):
    return [p["id"] for p in _items(client, headers)]


def test_a_student_sees_untouched_above_what_they_gave_aura(
        client, db, auth_headers, enrolled, klass, student, student2):
    liked = _mk(db, student2, klass, "liked", age_h=0)
    old = _mk(db, student2, klass, "old", age_h=24 * 5)
    db.add(Like(user_id=student.id, post_id=liked.id))
    db.commit()
    ids = _ids(client, auth_headers)
    assert ids.index(old.id) < ids.index(liked.id)


def test_a_pending_participacion_goes_on_top_until_validated(
        client, db, teacher_headers, klass, teacher, student, enrolled, student2):
    part = _mk(db, student, klass, "part", age_h=3, type="participacion", taps=1)
    fresh = _mk(db, student2, klass, "fresh", age_h=0)
    assert _ids(client, teacher_headers)[:2] == [part.id, fresh.id]
    part.reviewed_at = utcnow()
    db.add(Like(user_id=teacher.id, post_id=part.id))
    db.commit()
    ids = _ids(client, teacher_headers)
    assert ids.index(fresh.id) < ids.index(part.id)


def test_a_vetoed_participacion_is_not_pending(client, db, teacher_headers, klass, student, enrolled):
    _mk(db, student, klass, "v", type="participacion", taps=1, status="vetoed")
    assert all(p["pending_count"] is None for p in _items(client, teacher_headers))
    assert _ids(client, teacher_headers)  # still listed, just not in tier 1


def test_an_ungraded_entrega_raises_its_tarea_with_a_count(
        client, db, teacher_headers, klass, teacher, student, enrolled, student2):
    tarea = _mk(db, teacher, klass, "tarea", age_h=24 * 3, type="tarea")
    fresh = _mk(db, student2, klass, "fresh", age_h=0)
    _mk(db, student, klass, "entrega", age_h=1, parent_id=tarea.id, is_entrega=True)
    items = _items(client, teacher_headers)
    assert items[0]["id"] == tarea.id and items[0]["pending_count"] == 1
    assert [p["id"] for p in items].index(fresh.id) > 0


def test_grading_clears_it_and_a_late_entrega_brings_it_back(
        client, db, teacher_headers, klass, teacher, student, enrolled, student2):
    tarea = _mk(db, teacher, klass, "tarea", age_h=24 * 3, type="tarea")
    e = _mk(db, student, klass, "entrega", age_h=2, parent_id=tarea.id, is_entrega=True)
    db.add(Review(item_post_id=tarea.id, student_id=student.id, entrega_post_id=e.id,
                  reviewer_id=teacher.id, score=90))
    db.commit()
    assert all(p["pending_count"] is None for p in _items(client, teacher_headers))
    _mk(db, student2, klass, "tarde", age_h=0, parent_id=tarea.id, is_entrega=True)
    items = _items(client, teacher_headers)
    assert items[0]["id"] == tarea.id and items[0]["pending_count"] == 1


def test_a_review_of_a_replaced_entrega_does_not_count(
        client, db, teacher_headers, klass, teacher, student, enrolled):
    tarea = _mk(db, teacher, klass, "tarea", age_h=48, type="tarea")
    old = _mk(db, student, klass, "v1", age_h=5, parent_id=tarea.id, is_entrega=True)
    db.add(Review(item_post_id=tarea.id, student_id=student.id, entrega_post_id=old.id,
                  reviewer_id=teacher.id, score=80))
    db.commit()
    _mk(db, student, klass, "v2", age_h=1, parent_id=tarea.id, is_entrega=True)
    items = _items(client, teacher_headers)
    assert items[0]["id"] == tarea.id and items[0]["pending_count"] == 1


def test_a_ghost_entrega_is_not_pending(client, db, teacher_headers, klass, teacher, ghost):
    tarea = _mk(db, teacher, klass, "tarea", age_h=48, type="tarea")
    _mk(db, ghost, klass, "entrega", age_h=1, parent_id=tarea.id, is_entrega=True)
    assert all(p["pending_count"] is None for p in _items(client, teacher_headers))


def test_an_examen_with_an_upload_is_pending_a_paper_one_is_not(
        client, db, teacher_headers, klass, teacher, student, enrolled):
    digital = _mk(db, teacher, klass, "digital", age_h=48, type="examen")
    paper = _mk(db, teacher, klass, "paper", age_h=48, type="examen")
    answer = _mk(db, student, klass, "", age_h=1, parent_id=digital.id)
    db.add(Attachment(post_id=answer.id, filename="a.pdf", content_type="application/pdf",
                      size=10, storage_key="k"))
    db.commit()
    items = {p["id"]: p for p in _items(client, teacher_headers)}
    assert items[digital.id]["pending_count"] == 1
    assert items[paper.id]["pending_count"] is None


def test_a_calificado_examen_is_not_pending(client, db, teacher_headers, klass, teacher, student, enrolled):
    ex = _mk(db, teacher, klass, "ex", age_h=48, type="examen", graded_at=utcnow())
    _mk(db, student, klass, "mi examen", age_h=1, parent_id=ex.id, is_entrega=True)
    assert all(p["pending_count"] is None for p in _items(client, teacher_headers))


def test_another_teachers_class_is_never_pending_for_me(client, db, teacher_headers, student):
    other_teacher = User(google_id="g-t2", email="t2@example.com", name="Otro", role="teacher")
    db.add(other_teacher)
    db.commit()
    other = Class(name="Otra", code="OTRA2026TIERS", teacher_id=other_teacher.id,
                  start_date=date(2026, 8, 17), end_date=date(2026, 12, 4), schedule_json=[])
    db.add(other)
    db.commit()
    db.add(Enrollment(user_id=student.id, class_id=other.id))
    db.commit()
    part = _mk(db, student, other, "part", age_h=200, type="participacion", taps=1)
    fresh = _mk(db, student, other, "fresh", age_h=0)
    ids = _ids(client, teacher_headers)
    assert ids.index(fresh.id) < ids.index(part.id)


def test_students_never_get_a_pending_count(client, db, auth_headers, klass, teacher, student, enrolled, student2):
    tarea = _mk(db, teacher, klass, "tarea", age_h=48, type="tarea")
    _mk(db, student2, klass, "entrega", age_h=1, parent_id=tarea.id, is_entrega=True)
    assert all(p["pending_count"] is None for p in _items(client, auth_headers))


def test_old_pending_still_comes_first(client, db, teacher_headers, klass, student, enrolled, student2):
    part = _mk(db, student, klass, "old part", age_h=24 * 30, type="participacion", taps=1)
    _mk(db, student2, klass, "fresh", age_h=0)
    assert _ids(client, teacher_headers)[0] == part.id


def test_paging_is_stable_while_the_teacher_validates(
        client, db, teacher_headers, klass, teacher, student, enrolled):
    ids = {_mk(db, student, klass, f"p{i}", age_h=i, type="participacion", taps=1).id
           for i in range(25)}
    seen, url = [], "/api/feed?limit=10"
    while url:
        body = client.get(url, headers=teacher_headers).json()
        page = [p["id"] for p in body["items"]]
        seen += page
        for pid in page:  # validate everything just seen
            db.get(Post, pid).reviewed_at = utcnow()
            db.add(Like(user_id=teacher.id, post_id=pid))
        db.commit()
        url = f"/api/feed?limit=10&cursor={body['next_cursor']}" if body["next_cursor"] else None
    assert len(seen) == len(set(seen)) and set(seen) == ids
```

Before running, check the `Attachment` model's required columns (`grep -n "class Attachment" -A14 backend/app/models.py`) and adjust the constructor in the examen test to match.

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_feed_tiers.py -q -p no:warnings`
Expected: most FAIL (`KeyError: 'pending_count'`, ordering); the student test may already pass via Task 1.

- [ ] **Step 3: `PostOut.pending_count`** — in `backend/app/schemas.py`, after `featured_reply`:

```python
    # Only on the teacher's /api/feed: entregas or exámenes left to grade.
    pending_count: Optional[int] = None
```

- [ ] **Step 4: `teacher_pending`** — append to `feed_query.py` (imports: `Optional` from typing, `or_` from sqlalchemy, `Class, Enrollment, Review` from `app.models`):

```python
def teacher_pending(db: Session, teacher_id: int,
                    as_of: datetime) -> Dict[int, Tuple[datetime, Optional[int]]]:
    """root id → (pending since, count) for the work that needs this teacher,
    as of as_of. Same meaning as /revisar: a participación not validated nor
    vetoed; a tarea whose counting entrega from an active student has no
    review; an examen not calificado with something uploaded and ungraded.
    Participaciones carry no count."""
    class_ids = [cid for (cid,) in db.query(Class.id).filter(Class.teacher_id == teacher_id)]
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

    for item in items:
        latest_entrega: Dict[int, tuple] = {}
        latest_upload: Dict[int, tuple] = {}
        for r in replies:
            if r.parent_id != item.id or (item.class_id, r.author_id) not in active:
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
```

Note: for an examen submitted as a plain upload (not an entrega), `rv.entrega_post_id` is set by the roster to the entrega id or `None`; a review with `entrega_post_id is None` counts. Keep the rule above.

- [ ] **Step 5: `ranked_page` takes `pending_at`**:

```python
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
    # (rest unchanged)
```

- [ ] **Step 6: `get_feed`** — after `my_class_ids = …`:

```python
    pending = teacher_pending(db, user.id, as_of) if user.role == "teacher" else {}
    ids, has_more = ranked_page(db, user.id, my_class_ids, as_of, offset, limit,
                                {pid: at for pid, (at, _) in pending.items()})
```

and in `out(p)`, after setting `featured_reply`:

```python
        count = pending.get(p.id, (None, None))[1]
        if count:
            o.pending_count = count
```

Import `teacher_pending` alongside the other `feed_query` imports.

- [ ] **Step 7: Run** — `cd backend && .venv/bin/python -m pytest tests/test_feed_tiers.py -q -p no:warnings`, then the full suite on SQLite and on local Postgres (`TEST_DATABASE_URL="postgresql+psycopg://$(whoami)@localhost:5432/school_app_test"`). All PASS.

- [ ] **Step 8: Commit** — `git commit -m "feat(feed): the teacher's pending work rises to the top"`

---

### Task 3: "N por calificar" badge, docs

**Files:**
- Modify: `frontend/src/lib/types.ts` (`Post.pending_count?: number | null`)
- Modify: `frontend/src/strings/es.ts` (`feed.toGrade: "{n} por calificar"`)
- Modify: `frontend/src/components/PostCard.tsx` (badge)
- Modify: `planning/roadmap.md`, `planning/changelog.md`

- [ ] **Step 1:** Add the type and string. In `PostCard.tsx`, right after the Tarea badge block and after the Examen badge block, render (once, keyed on `pending_count`):

```tsx
        {post.pending_count != null && post.pending_count > 0 && !removed && (
          <span className="mt-1 ml-1 inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            {es.feed.toGrade.replace("{n}", String(post.pending_count))}
          </span>
        )}
```

Place it once, after the Examen badge block, so it follows whichever badge the card has.

- [ ] **Step 2:** `cd frontend && npm run lint && npm run build && npm test` → PASS.

- [ ] **Step 3:** Roadmap: under Bloque 4 add `- [x] **Bloque 4b — capas del feed** ✅ 2026-10-21 (spec 2026-10-21-feed-tiers-design.md): lo que tocaste va debajo de todo lo nuevo; para el profe, lo pendiente (participaciones por validar, tareas y exámenes por calificar) va arriba, lo más reciente primero.` Changelog: add to the 2026-10-21 entry a bullet in Spanish describing the same, in the existing style.

- [ ] **Step 4: Commit** — `git commit -m "feat(feed): N por calificar badge; roadmap and changelog for Bloque 4b"`
