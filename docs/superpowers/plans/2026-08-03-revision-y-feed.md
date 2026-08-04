# Revisión y feed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the teacher mark participaciones as seen without cancelling them, pin a student's open tareas above the feed, and stop assignments from other classes appearing at all.

**Architecture:** Two nullable columns on `posts` carry "a teacher looked at this", kept entirely separate from `status`, which carries "this counts". Pinned tareas ride in their own array outside pagination. The feed query gains a class filter that applies only to `tarea` and `examen`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 typed `Mapped[]`, Alembic, pytest; React 19 + Vite + TanStack Query + Tailwind, shadcn preset `base-sera`, `@remixicon/react`, vitest.

## Global Constraints

- Source of truth: `docs/superpowers/specs/2026-08-03-revision-y-feed-design.md`. Where this plan and the spec disagree, the spec wins.
- **Nothing here moves a point.** No `points_ledger` writes, no grade-engine changes. A test in Task 2 pins this.
- `validar` and `vetar` must never be collapsed into one action or made to look alike. Conflating them is what cancelled real participaciones on 2026-08-03.
- Preset components used as they arrive — no restyling a primitive, no editing `--radius` (`CLAUDE.md`).
- One control per line in forms; list rows pairing a person with a control are the exception.
- All copy is a placeholder in `frontend/src/strings/es.ts`. Mario writes final copy.
- Backend tests: `../venv/bin/python -m pytest` from `backend/`, currently **202 passing**. Frontend: `npx vitest run && npx tsc --noEmit && npm run lint` from `frontend/`, currently **24 passing**.
- Deploy only when Mario says so — students are using `main` mid-semester.

---

### Task 1: Schema — `reviewed_at` and `reviewed_by`

**Files:**
- Modify: `backend/app/models.py` (`Post`)
- Create: `backend/alembic/versions/<generated>_participacion_reviewed.py`
- Test: `backend/tests/test_migrations.py`

**Interfaces:**
- Produces: `Post.reviewed_at: Optional[datetime]`, `Post.reviewed_by: Optional[int]`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_migrations.py`:

```python
def test_posts_has_reviewed_columns(db):
    from sqlalchemy import inspect

    cols = {c["name"] for c in inspect(db.bind).get_columns("posts")}
    assert {"reviewed_at", "reviewed_by"} <= cols
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_migrations.py -k reviewed -v`
Expected: FAIL — the columns do not exist.

- [ ] **Step 3: Add the columns**

In `backend/app/models.py`, add to `Post` immediately after `veto_reason`:

```python
    # "A teacher looked at this." Deliberately separate from `status`, which
    # says whether it counts. Validating never moves a point; vetoing does.
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
```

- [ ] **Step 4: Generate the migration**

Run: `cd backend && ../venv/bin/python -m alembic revision --autogenerate -m "participacion reviewed"`

Check the generated file contains exactly:

```python
def upgrade() -> None:
    op.add_column('posts', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('posts', sa.Column('reviewed_by', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'posts', 'users', ['reviewed_by'], ['id'])


def downgrade() -> None:
    op.drop_constraint(None, 'posts', type_='foreignkey')
    op.drop_column('posts', 'reviewed_by')
    op.drop_column('posts', 'reviewed_at')
```

If autogenerate names the FK constraint `None`, give it an explicit name — `fk_posts_reviewed_by_users` — in both directions. PostgreSQL needs a real name to drop it, and the migration chain is applied against PostgreSQL in CI.

- [ ] **Step 5: Run the full suite**

Run: `cd backend && ../venv/bin/python -m pytest -q`
Expected: PASS, 203.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/alembic/versions backend/tests/test_migrations.py
git commit -m "feat(backend): reviewed_at and reviewed_by on posts"
```

---

### Task 2: Mark a participación as reviewed

**Files:**
- Modify: `backend/app/routers/posts.py`
- Test: `backend/tests/test_reviewed.py` (create)

**Interfaces:**
- Consumes: `_teacher_of_post(db, post_id, user) -> Post` — already in `posts.py`, used by the veto endpoints.
- Produces: `POST /api/posts/{id}/reviewed` and `DELETE /api/posts/{id}/reviewed`, both returning `{"reviewed": bool}`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_reviewed.py`:

```python
from decimal import Decimal

from app.models import PointsLedger, Post


def _participacion(client, headers):
    return client.post("/api/posts", data={
        "content": "Expliqué el modelo de oferta y demanda",
        "type": "participacion", "taps": "3",
    }, headers=headers)


def _active_points(db, user_id) -> Decimal:
    rows = db.query(PointsLedger).filter(PointsLedger.user_id == user_id,
                                         PointsLedger.revoked_at.is_(None)).all()
    return sum((r.points for r in rows), Decimal("0"))


def test_reviewing_moves_no_points(client, db, teacher_headers, auth_headers, student, enrolled):
    """The whole point of validar: it records attention, never a grade."""
    pid = _participacion(client, auth_headers).json()["id"]
    before = _active_points(db, student.id)
    r = client.post(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    assert r.status_code == 200
    assert r.json()["reviewed"] is True
    db.expire_all()
    assert _active_points(db, student.id) == before
    assert db.get(Post, pid).status == "active"


def test_unreviewing_returns_it_to_pending(client, db, teacher_headers, auth_headers, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    client.post(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    r = client.delete(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    assert r.json()["reviewed"] is False
    db.expire_all()
    assert db.get(Post, pid).reviewed_at is None
    assert db.get(Post, pid).reviewed_by is None


def test_reviewing_records_who_looked(client, db, teacher_headers, auth_headers, teacher, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    client.post(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    db.expire_all()
    assert db.get(Post, pid).reviewed_by == teacher.id


def test_a_student_cannot_review(client, auth_headers, student2_headers, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    r = client.post(f"/api/posts/{pid}/reviewed", headers=student2_headers)
    assert r.status_code == 403


def test_only_participaciones_can_be_reviewed(client, db, teacher_headers, auth_headers, enrolled):
    pid = client.post("/api/posts", data={"content": "hola"},
                      headers=auth_headers).json()["id"]
    r = client.post(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    assert r.status_code == 422


def test_reviewing_and_vetoing_are_independent(client, db, teacher_headers, auth_headers, student, enrolled):
    """Both facts coexist: a post can be seen and still count, or be cancelled
    without ever having been marked seen."""
    pid = _participacion(client, auth_headers).json()["id"]
    client.post(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    client.post(f"/api/posts/{pid}/veto", headers=teacher_headers)
    db.expire_all()
    post = db.get(Post, pid)
    assert post.reviewed_at is not None      # still marked as seen
    assert post.status == "vetoed"           # and cancelled
    assert _active_points(db, student.id) == Decimal("0")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_reviewed.py -v`
Expected: FAIL — 404/405, the routes do not exist.

- [ ] **Step 3: Implement**

Append to `backend/app/routers/posts.py`, next to the veto endpoints:

```python
def _teacher_participacion(db: Session, post_id: int, user: User) -> Post:
    post = _teacher_of_post(db, post_id, user)
    if post.type != "participacion":
        raise HTTPException(status_code=422,
                            detail="Sólo las participaciones se revisan")
    return post


@router.post("/{post_id}/reviewed")
def mark_reviewed(post_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Records that the teacher looked. Moves no points — the student earned
    them on publish. This is the non-destructive twin of veto."""
    post = _teacher_participacion(db, post_id, user)
    post.reviewed_at = utcnow()
    post.reviewed_by = user.id
    db.commit()
    return {"reviewed": True}


@router.delete("/{post_id}/reviewed")
def unmark_reviewed(post_id: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    post = _teacher_participacion(db, post_id, user)
    post.reviewed_at = None
    post.reviewed_by = None
    db.commit()
    return {"reviewed": False}
```

- [ ] **Step 4: Run the full suite**

Run: `cd backend && ../venv/bin/python -m pytest -q`
Expected: PASS, 209.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/posts.py backend/tests/test_reviewed.py
git commit -m "feat(backend): mark a participación as reviewed without touching points"
```

---

### Task 3: Bulk review, all-or-nothing

**Files:**
- Modify: `backend/app/routers/review_queue.py`, `backend/app/schemas.py`
- Test: `backend/tests/test_reviewed.py`

**Interfaces:**
- Produces: `POST /api/review/participaciones/reviewed` with body `{"post_ids": [int]}`, returning `{"reviewed": int}`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_reviewed.py`:

```python
def test_bulk_reviews_every_id_sent(client, db, teacher_headers, auth_headers, enrolled):
    ids = [_participacion(client, auth_headers).json()["id"] for _ in range(3)]
    r = client.post("/api/review/participaciones/reviewed",
                    json={"post_ids": ids}, headers=teacher_headers)
    assert r.status_code == 200
    assert r.json()["reviewed"] == 3
    db.expire_all()
    assert all(db.get(Post, i).reviewed_at is not None for i in ids)


def test_bulk_with_a_foreign_id_writes_nothing(client, db, teacher_headers, auth_headers, teacher, enrolled):
    """All-or-nothing: a partial write would leave the teacher unable to tell
    which taps landed."""
    from datetime import date

    from app.auth.sessions import create_session
    from app.models import Class, Enrollment, User

    other_teacher = User(google_id="g-other3", email="otro3@example.com",
                         name="Otra", role="teacher")
    db.add(other_teacher)
    db.commit()
    other_class = Class(name="Otra", code="OTRA2026X", teacher_id=other_teacher.id,
                        start_date=date(2026, 8, 17), end_date=date(2026, 12, 4),
                        schedule_json=[])
    db.add(other_class)
    db.commit()
    outsider = User(google_id="g-out", email="out@example.com", name="Out")
    db.add(outsider)
    db.commit()
    db.add(Enrollment(user_id=outsider.id, class_id=other_class.id))
    db.commit()
    out_headers = {"Authorization": f"Bearer {create_session(db, outsider)}"}
    foreign = client.post("/api/posts", data={
        "content": "Participación de otra clase", "type": "participacion",
        "taps": "1",
    }, headers=out_headers).json()["id"]

    mine = _participacion(client, auth_headers).json()["id"]
    r = client.post("/api/review/participaciones/reviewed",
                    json={"post_ids": [mine, foreign]}, headers=teacher_headers)
    assert r.status_code == 403
    db.expire_all()
    assert db.get(Post, mine).reviewed_at is None      # nothing written
    assert db.get(Post, foreign).reviewed_at is None


def test_bulk_with_an_empty_list_is_a_no_op(client, teacher_headers):
    r = client.post("/api/review/participaciones/reviewed",
                    json={"post_ids": []}, headers=teacher_headers)
    assert r.status_code == 200
    assert r.json()["reviewed"] == 0


def test_a_student_cannot_bulk_review(client, auth_headers, student2_headers, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    r = client.post("/api/review/participaciones/reviewed",
                    json={"post_ids": [pid]}, headers=student2_headers)
    assert r.status_code == 403
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_reviewed.py -k bulk -v`
Expected: FAIL — 404, the route does not exist.

- [ ] **Step 3: Add the schema**

In `backend/app/schemas.py`:

```python
class BulkReviewIn(BaseModel):
    post_ids: List[int]
```

Use the module's existing `List` import; add `from typing import List` only if absent.

- [ ] **Step 4: Implement**

Append to `backend/app/routers/review_queue.py`:

```python
@router.post("/participaciones/reviewed")
def bulk_reviewed(body: BulkReviewIn, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Marks exactly the ids sent. The client sends what is on screen, never
    "everything pending" — a participación published mid-scroll must not be
    marked as seen by a tap made before it existed.

    All-or-nothing: one foreign id rejects the whole batch, because a partial
    write would leave the teacher unable to tell which taps landed."""
    if not body.post_ids:
        return {"reviewed": 0}
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Solo el profesor puede revisar")

    posts = db.query(Post).filter(Post.id.in_(body.post_ids)).all()
    if len(posts) != len(set(body.post_ids)):
        raise HTTPException(status_code=404, detail="Publicación no encontrada")

    owned = {
        cid for (cid,) in db.query(Class.id).filter(Class.teacher_id == user.id).all()
    }
    for post in posts:
        if post.type != "participacion":
            raise HTTPException(status_code=422,
                                detail="Sólo las participaciones se revisan")
        if post.class_id not in owned:
            raise HTTPException(status_code=403,
                                detail="No eres profesor de esa clase")

    now = utcnow()
    for post in posts:
        post.reviewed_at = now
        post.reviewed_by = user.id
    db.commit()
    return {"reviewed": len(posts)}
```

Extend the imports at the top of the file to include `utcnow` and `BulkReviewIn`.

- [ ] **Step 5: Run the full suite**

Run: `cd backend && ../venv/bin/python -m pytest -q`
Expected: PASS, 213.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/review_queue.py backend/app/schemas.py backend/tests/test_reviewed.py
git commit -m "feat(backend): bulk review, all-or-nothing on the ids sent"
```

---

### Task 4: The queue splits pending from handled

**Files:**
- Modify: `backend/app/routers/review_queue.py` (`participaciones`)
- Test: `backend/tests/test_review_queue.py`

**Interfaces:**
- Produces: `GET /api/review/participaciones?class_id=&status=pending|handled&limit=`; each row gains `reviewed: bool`. Default `status` is `pending`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_review_queue.py`:

```python
def _part(client, headers, text="Participé explicando el modelo"):
    return client.post("/api/posts", data={
        "content": text, "type": "participacion", "taps": "2",
    }, headers=headers).json()["id"]


def test_pending_excludes_reviewed_and_vetoed(client, db, teacher_headers, auth_headers, klass, enrolled):
    plain = _part(client, auth_headers)
    seen = _part(client, auth_headers)
    killed = _part(client, auth_headers)
    client.post(f"/api/posts/{seen}/reviewed", headers=teacher_headers)
    client.post(f"/api/posts/{killed}/veto", headers=teacher_headers)

    r = client.get(f"/api/review/participaciones?class_id={klass.id}&status=pending",
                   headers=teacher_headers)
    ids = [i["post_id"] for i in r.json()["items"]]
    assert plain in ids
    assert seen not in ids
    assert killed not in ids


def test_handled_holds_both_reviewed_and_vetoed(client, db, teacher_headers, auth_headers, klass, enrolled):
    seen = _part(client, auth_headers)
    killed = _part(client, auth_headers)
    client.post(f"/api/posts/{seen}/reviewed", headers=teacher_headers)
    client.post(f"/api/posts/{killed}/veto", headers=teacher_headers)

    r = client.get(f"/api/review/participaciones?class_id={klass.id}&status=handled",
                   headers=teacher_headers)
    ids = [i["post_id"] for i in r.json()["items"]]
    assert seen in ids and killed in ids


def test_rows_carry_the_reviewed_flag(client, db, teacher_headers, auth_headers, klass, enrolled):
    seen = _part(client, auth_headers)
    client.post(f"/api/posts/{seen}/reviewed", headers=teacher_headers)
    r = client.get(f"/api/review/participaciones?class_id={klass.id}&status=handled",
                   headers=teacher_headers)
    row = next(i for i in r.json()["items"] if i["post_id"] == seen)
    assert row["reviewed"] is True
    assert row["vetoed"] is False
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_review_queue.py -k "pending or handled or reviewed_flag" -v`
Expected: FAIL — the endpoint ignores `status` and returns everything.

- [ ] **Step 3: Implement**

Replace the `participaciones` handler's query and row-building in `backend/app/routers/review_queue.py`:

```python
@router.get("/participaciones")
def participaciones(class_id: int, status: str = Query("pending"),
                    limit: int = Query(50, ge=1, le=200),
                    user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    klass = _owned_class(db, class_id, user)
    q = db.query(Post).filter(Post.class_id == klass.id,
                              Post.type == "participacion")
    # Pending means "still needs you": not looked at, and not cancelled.
    if status == "pending":
        q = q.filter(Post.reviewed_at.is_(None), Post.status != "vetoed")
    else:
        q = q.filter(or_(Post.reviewed_at.isnot(None), Post.status == "vetoed"))
    posts = q.order_by(Post.created_at.desc()).limit(limit).all()
```

Add `reviewed` to each item dict:

```python
            "reviewed": p.reviewed_at is not None,
```

Add `from sqlalchemy import or_` to the imports.

- [ ] **Step 4: Run the full suite**

Run: `cd backend && ../venv/bin/python -m pytest -q`
Expected: PASS, 216.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/review_queue.py backend/tests/test_review_queue.py
git commit -m "feat(backend): participaciones queue splits pending from handled"
```

---

### Task 5: Assignments are scoped to their class

**Files:**
- Modify: `backend/app/routers/posts.py` (`get_feed`)
- Test: `backend/tests/test_feed_scoping.py` (create)

**Interfaces:**
- Produces: `GET /api/feed` excludes `tarea` and `examen` posts whose class the viewer is not in.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_feed_scoping.py`:

```python
from datetime import date, datetime, timedelta, timezone

from app.auth.sessions import create_session
from app.models import Class, Enrollment, Post, User

SOON = datetime(2026, 12, 1, tzinfo=timezone.utc)


def _other_class_with_tarea(db):
    t = User(google_id="g-t2", email="t2@example.com", name="Profe2", role="teacher")
    db.add(t)
    db.commit()
    k = Class(name="Otra", code="OTRA2026Z", teacher_id=t.id,
              start_date=date(2026, 8, 17), end_date=date(2026, 12, 4),
              schedule_json=[])
    db.add(k)
    db.commit()
    tarea = Post(author_id=t.id, class_id=k.id, type="tarea",
                 content="Tarea de otra clase", due_date=SOON)
    regular = Post(author_id=t.id, class_id=k.id, type="regular",
                   content="Post normal de otra clase")
    db.add_all([tarea, regular])
    db.commit()
    return tarea, regular


def _feed_ids(client, headers):
    return [p["id"] for p in client.get("/api/feed", headers=headers).json()["items"]]


def test_a_tarea_from_another_class_is_not_in_your_feed(client, db, auth_headers, enrolled):
    """A student confidently mistaking another class's homework for their own
    is the harm this prevents."""
    tarea, _ = _other_class_with_tarea(db)
    assert tarea.id not in _feed_ids(client, auth_headers)


def test_a_regular_post_from_another_class_still_is(client, db, auth_headers, enrolled):
    """The feed stays global for social content — that is the product."""
    _, regular = _other_class_with_tarea(db)
    assert regular.id in _feed_ids(client, auth_headers)


def test_your_own_class_tarea_is_in_your_feed(client, db, teacher, auth_headers, klass, enrolled):
    tarea = Post(author_id=teacher.id, class_id=klass.id, type="tarea",
                 content="Mi tarea", due_date=SOON)
    db.add(tarea)
    db.commit()
    assert tarea.id in _feed_ids(client, auth_headers)


def test_the_teacher_sees_their_own_class_tarea(client, db, teacher, teacher_headers, klass):
    tarea = Post(author_id=teacher.id, class_id=klass.id, type="tarea",
                 content="Mi tarea", due_date=SOON)
    db.add(tarea)
    db.commit()
    assert tarea.id in _feed_ids(client, teacher_headers)


def test_a_ghost_still_sees_their_class_tarea(client, db, teacher, ghost, klass):
    """Ghost and polizón are legitimately in the class; they earn no points but
    the class's work is still theirs to read."""
    tarea = Post(author_id=teacher.id, class_id=klass.id, type="tarea",
                 content="Mi tarea", due_date=SOON)
    db.add(tarea)
    db.commit()
    headers = {"Authorization": f"Bearer {create_session(db, ghost)}"}
    assert tarea.id in _feed_ids(client, headers)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_feed_scoping.py -v`
Expected: FAIL on the first test — the feed has no class filter, so the foreign tarea appears.

- [ ] **Step 3: Implement**

In `get_feed` in `backend/app/routers/posts.py`, after building the base query:

```python
    # Social content is global — all classes, all semesters. Assignments are
    # not: a student cannot tell another class's tarea from work they owe, and
    # that confusion is worse than the loss of reach.
    my_class_ids = [
        cid for (cid,) in db.query(Enrollment.class_id)
        .filter(Enrollment.user_id == user.id).all()
    ]
    my_class_ids += [
        cid for (cid,) in db.query(Class.id)
        .filter(Class.teacher_id == user.id).all()
    ]
    q = q.filter(or_(
        Post.type.notin_(("tarea", "examen")),
        Post.class_id.in_(my_class_ids),
    ))
```

`in_([])` on an empty list renders as a false condition in SQLAlchemy 2.0, which is exactly right here — someone enrolled in nothing sees no assignments. Do **not** write `if my_class_ids else False`; a bare Python `False` inside `or_()` is not a SQL expression.

Note the enrollment query has **no status filter**: `active`, `ghost` and `polizon` are all in the class (spec §2.4).

- [ ] **Step 4: Run the full suite**

Run: `cd backend && ../venv/bin/python -m pytest -q`
Expected: PASS, 221.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/posts.py backend/tests/test_feed_scoping.py
git commit -m "feat(backend): tareas and examenes only reach their own class"
```

---

### Task 6: Pinned tareas

**Files:**
- Modify: `backend/app/routers/posts.py` (`get_feed`)
- Test: `backend/tests/test_feed_pinned.py` (create)

**Interfaces:**
- Produces: `GET /api/feed` response gains `pinned: [PostOut]`, ordered by `due_date` ascending. Not paginated; identical on every page.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_feed_pinned.py`:

```python
from datetime import datetime, timedelta, timezone

from app.models import Post

NOW = datetime.now(timezone.utc)
SOON = NOW + timedelta(days=3)
LATER = NOW + timedelta(days=10)
PAST = NOW - timedelta(days=1)


def _tarea(db, teacher, klass, due):
    p = Post(author_id=teacher.id, class_id=klass.id, type="tarea",
             content=f"Tarea {due.date()}", due_date=due)
    db.add(p)
    db.commit()
    return p


def _pinned_ids(client, headers):
    return [p["id"] for p in client.get("/api/feed", headers=headers).json()["pinned"]]


def test_an_open_tarea_is_pinned(client, db, teacher, auth_headers, klass, enrolled):
    t = _tarea(db, teacher, klass, SOON)
    assert _pinned_ids(client, auth_headers) == [t.id]


def test_a_past_due_tarea_is_not_pinned(client, db, teacher, auth_headers, klass, enrolled):
    _tarea(db, teacher, klass, PAST)
    assert _pinned_ids(client, auth_headers) == []


def test_delivering_unpins_it_for_you(client, db, teacher, student, auth_headers, klass, enrolled):
    t = _tarea(db, teacher, klass, SOON)
    db.add(Post(author_id=student.id, class_id=klass.id, type="regular",
                parent_id=t.id, content="mi entrega", is_entrega=True))
    db.commit()
    assert _pinned_ids(client, auth_headers) == []


def test_it_stays_pinned_for_a_classmate_who_has_not_delivered(
    client, db, teacher, student, auth_headers, student2_headers, klass, enrolled
):
    t = _tarea(db, teacher, klass, SOON)
    db.add(Post(author_id=student.id, class_id=klass.id, type="regular",
                parent_id=t.id, content="mi entrega", is_entrega=True))
    db.commit()
    assert _pinned_ids(client, auth_headers) == []
    assert _pinned_ids(client, student2_headers) == [t.id]


def test_soonest_deadline_first(client, db, teacher, auth_headers, klass, enrolled):
    later = _tarea(db, teacher, klass, LATER)
    soon = _tarea(db, teacher, klass, SOON)
    assert _pinned_ids(client, auth_headers) == [soon.id, later.id]


def test_another_class_tarea_is_never_pinned(client, db, auth_headers, enrolled):
    from tests.test_feed_scoping import _other_class_with_tarea

    tarea, _ = _other_class_with_tarea(db)
    assert tarea.id not in _pinned_ids(client, auth_headers)


def test_pinned_is_identical_on_every_page(client, db, teacher, auth_headers, klass, enrolled, student):
    t = _tarea(db, teacher, klass, SOON)
    for i in range(25):
        db.add(Post(author_id=student.id, class_id=klass.id, content=f"p{i}"))
    db.commit()
    first = client.get("/api/feed?limit=20", headers=auth_headers).json()
    assert [p["id"] for p in first["pinned"]] == [t.id]
    second = client.get(
        f"/api/feed?limit=20&cursor={first['next_cursor']}", headers=auth_headers
    ).json()
    assert [p["id"] for p in second["pinned"]] == [t.id]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_feed_pinned.py -v`
Expected: FAIL — `KeyError: 'pinned'`.

- [ ] **Step 3: Implement**

Add to `backend/app/routers/posts.py` above `get_feed`:

```python
def _pinned_tareas(db: Session, user: User, class_ids: List[int]) -> List[Post]:
    """Open tareas the viewer has not delivered yet.

    Kept out of the paginated query on purpose: pinning inside it would mean
    ordering by a per-student, time-dependent condition on top of a keyset
    cursor over a mutable sort key, which is the same fragility that made
    likes reorder the feed under the reader.
    """
    if not class_ids:
        return []
    tareas = (
        db.query(Post)
        .options(selectinload(Post.author), selectinload(Post.klass),
                 selectinload(Post.attachments))
        .filter(Post.type == "tarea", Post.status == "active",
                Post.class_id.in_(class_ids),
                Post.due_date.isnot(None), Post.due_date > utcnow())
        .order_by(Post.due_date.asc())
        .all()
    )
    return [t for t in tareas
            if _counting_entrega(db, user.id, t.id) is None]
```

Import `_counting_entrega` from `app.services.grades`.

In `get_feed`, reuse the `my_class_ids` list built in Task 5 and return the new key:

```python
    pinned = _pinned_tareas(db, user, my_class_ids)
    liked = _liked_ids(db, user, [p.id for p in posts] + [p.id for p in pinned])
    return {"items": [serialize_post(p, liked, viewer=user) for p in posts],
            "pinned": [serialize_post(p, liked, viewer=user) for p in pinned],
            "next_cursor": next_cursor}
```

- [ ] **Step 4: Run the full suite**

Run: `cd backend && ../venv/bin/python -m pytest -q`
Expected: PASS, 228.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/posts.py backend/tests/test_feed_pinned.py
git commit -m "feat(backend): open tareas pinned above the feed until delivered"
```

---

### Task 7: Validar in the Revisar queue

**Files:**
- Modify: `frontend/src/pages/Revisar.tsx`, `frontend/src/lib/review.ts`, `frontend/src/lib/types.ts`, `frontend/src/strings/es.ts`
- Test: `frontend/src/lib/review.test.ts`

**Interfaces:**
- Consumes: Tasks 2–4.
- Produces: `setReviewed(postId: number, reviewed: boolean)` and `bulkReviewed(postIds: number[])` in `frontend/src/lib/review.ts`; `ParticipacionRow` gains `reviewed: boolean`.

- [ ] **Step 1: Add the strings**

In `frontend/src/strings/es.ts`, add to the `revisar` block:

```ts
    validar: "Validar",
    validarTodas: "Validar todas ({n})",
    validated: "Validada",
    unvalidate: "Marcar como no vista",
    vetoConfirmTitle: "¿Vetar esta participación?",
    vetoConfirmBody:
      "Vetar le quita los puntos al alumno. Validar sólo marca que ya la viste y no cambia su calificación.",
    vetoConfirmYes: "Vetar y quitar puntos",
```

The confirmation copy names both actions on purpose: the incident happened because nothing on screen said what the difference was.

- [ ] **Step 2: Add the client functions**

In `frontend/src/lib/review.ts`:

```ts
export function setReviewed(postId: number, reviewed: boolean) {
  return api<{ reviewed: boolean }>(`/api/posts/${postId}/reviewed`, {
    method: reviewed ? "POST" : "DELETE",
  });
}

/** Sends exactly the ids on screen. Never "everything pending" — a
 *  participación published mid-scroll must not be marked as seen. */
export function bulkReviewed(postIds: number[]) {
  return api<{ reviewed: number }>("/api/review/participaciones/reviewed", {
    method: "POST",
    body: JSON.stringify({ post_ids: postIds }),
  });
}
```

In `frontend/src/lib/types.ts`, add `reviewed: boolean;` to `ParticipacionRow`.

- [ ] **Step 3: Write the failing test**

Append to `frontend/src/lib/review.test.ts`:

```ts
import { bulkReviewed } from "./review";

describe("bulkReviewed", () => {
  it("sends exactly the ids given, in order", async () => {
    const calls: { url: string; body: unknown }[] = [];
    const original = globalThis.fetch;
    globalThis.fetch = (async (url: string, init: RequestInit) => {
      calls.push({ url, body: JSON.parse(init.body as string) });
      return new Response(JSON.stringify({ reviewed: 2 }), { status: 200 });
    }) as typeof fetch;

    await bulkReviewed([7, 3]);
    globalThis.fetch = original;

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe("/api/review/participaciones/reviewed");
    expect(calls[0].body).toEqual({ post_ids: [7, 3] });
  });
});
```

- [ ] **Step 4: Run it**

Run: `cd frontend && npx vitest run src/lib/review.test.ts`
Expected: PASS once `bulkReviewed` exists; FAIL beforehand with an import error.

- [ ] **Step 5: Wire the tab**

In `ParticipacionesTab` in `frontend/src/pages/Revisar.tsx`:

Fetch with `&status=${showHandled ? "handled" : "pending"}` and delete the client-side `.filter` — the server decides membership now. Keep the existing optimistic pattern for every mutation: patch the row, roll back visibly on error, invalidate on settle.

The bulk button, rendered above the list when `!showHandled && rows.length > 0`:

```tsx
        <Button
          className="w-full"
          disabled={bulk.isPending}
          onClick={() => bulk.mutate(rows.map((r) => r.post_id))}
        >
          {es.revisar.validarTodas.replace("{n}", String(rows.length))}
        </Button>
```

```tsx
  const bulk = useMutation({
    // rows, not "everything pending": the ids are whatever is on screen.
    mutationFn: (ids: number[]) => bulkReviewed(ids),
    onError: () => toast.show(es.revisar.saveError),
    onSettled: () => void qc.invalidateQueries({ queryKey: key }),
  });
```

Each row's actions — validar is quiet, vetar is destructive and asks first:

```tsx
          <span className="flex shrink-0 gap-1">
            {!i.vetoed && (
              <Button
                variant={i.reviewed ? "outline" : "secondary"}
                size="sm"
                onClick={() =>
                  review.mutate({ postId: i.post_id, reviewed: !i.reviewed })
                }
              >
                {i.reviewed ? es.revisar.unvalidate : es.revisar.validar}
              </Button>
            )}
            <Button
              variant={i.vetoed ? "outline" : "destructive"}
              size="sm"
              onClick={() =>
                i.vetoed
                  ? toggle.mutate({ postId: i.post_id, vetoed: false })
                  : setConfirmingVeto(i)
              }
            >
              {i.vetoed ? es.revisar.unveto : es.revisar.veto}
            </Button>
          </span>
```

Un-vetoing fires directly — restoring points needs no warning. Vetoing routes through a `Dialog` whose body is `vetoConfirmBody`, which names *both* actions so the difference is stated at the moment of choosing:

```tsx
      <Dialog
        open={confirmingVeto != null}
        onOpenChange={() => setConfirmingVeto(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{es.revisar.vetoConfirmTitle}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {es.revisar.vetoConfirmBody}
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmingVeto(null)}>
              {es.configurar.cancel}
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (confirmingVeto)
                  toggle.mutate({ postId: confirmingVeto.post_id, vetoed: true });
                setConfirmingVeto(null);
              }}
            >
              {es.revisar.vetoConfirmYes}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
```

- [ ] **Step 6: Verify**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run`
Expected: all pass.

- [ ] **Step 7: Check it by hand**

Publish three participaciones as students. Validate one — confirm it leaves Pendientes, appears in Vistas, and **the student's grade chip does not change**. Veto one — confirm the dialog appears and names both actions. Use "Validar todas" and confirm the count matches what was on screen.

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): validar participaciones, with veto behind a confirmation"
```

---

### Task 8: Pinned tareas in the feed

**Files:**
- Modify: `frontend/src/pages/Home.tsx`, `frontend/src/lib/types.ts`, `frontend/src/strings/es.ts`

**Interfaces:**
- Consumes: `pinned` from Task 6.
- Produces: no new exports. `FeedPage` gains `pinned: Post[]`.

- [ ] **Step 1: Extend the type and strings**

In `frontend/src/lib/types.ts`:

```ts
export interface FeedPage {
  items: Post[];
  pinned: Post[];
  next_cursor: string | null;
}
```

In `frontend/src/strings/es.ts`, add to `feed`:

```ts
    pinnedHeader: "Por entregar",
```

- [ ] **Step 2: Render it**

In `frontend/src/pages/Home.tsx`, take `pinned` from the **first** page only — every page carries the same list, and merging them would repeat it:

```tsx
  const pinned = q.data.pages[0]?.pinned ?? [];
```

Render above the scroll, before the `posts.map`:

```tsx
      {pinned.length > 0 && (
        <section className="border-b bg-muted/40">
          <p className="px-4 pt-3 text-[10px] font-semibold tracking-widest uppercase text-muted-foreground">
            {es.feed.pinnedHeader}
          </p>
          <div className="divide-y">
            {pinned.map((p) => (
              <PostCard
                key={`pinned-${p.id}`}
                post={p}
                onLike={(post) => like.mutate(post)}
              />
            ))}
          </div>
        </section>
      )}
```

The `pinned-` key prefix matters: the same post can also appear in `items`, and React needs the two instances to have distinct keys.

- [ ] **Step 3: Verify**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run && npm run build`
Expected: all pass. `feed.test.ts`'s `post()` helper builds `Post`, not `FeedPage`, so it needs no change; if any fixture builds a `FeedPage` literal, add `pinned: []`.

- [ ] **Step 4: Check it by hand**

As a teacher, publish a tarea due next week. As a student in that class, confirm it appears under "Por entregar" at the top and also in the normal feed. Reply with the entrega toggle on, and confirm it disappears from the pinned section but stays in the feed. As a student in a *different* class, confirm it appears nowhere at all.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): open tareas pinned above the feed"
```

---

### Task 9: Close out

**Files:**
- Modify: `CLAUDE.md`, `docs/superpowers/specs/2026-07-19-v2-platform-rebuild-design.md`, `planning/changelog.md`

- [ ] **Step 1: Run everything**

```bash
cd backend && ../venv/bin/python -m pytest -q
cd ../frontend && npx vitest run && npx tsc --noEmit && npm run lint && npm run build
```

Record the real counts.

- [ ] **Step 2: Amend both documents**

`CLAUDE.md`, Core Model Rules — the line reading "The feed is **global** (all classes, all semesters)" gains: assignments are the exception, `tarea` and `examen` reach only their own class, because a student cannot distinguish another class's homework from work they owe.

Same amendment to line 59 of `docs/superpowers/specs/2026-07-19-v2-platform-rebuild-design.md`.

Also add to Core Model Rules: **validar ≠ vetar.** `reviewed_at` records that the teacher looked and moves no points; veto cancels. Never collapse them into one control.

Leaving a document contradicting the code is how the delete/veto rule stayed inverted for two weeks.

- [ ] **Step 3: Changelog**

Add a dated Spanish entry: what shipped, why validar had to be separate from vetar, why pinned lives outside pagination, and the scoping rule with its reasoning.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/ planning/
git commit -m "docs: close out revisión y feed"
```

---

## Notes for the reviewer

- **Nothing in this plan moves a point.** `test_reviewing_moves_no_points` in Task 2 is the guard. If a change makes it fail, the change is wrong.
- Validar and vetar must stay visibly distinct. Task 7 puts veto behind a confirmation that names both; removing it re-opens the trap that cancelled real participaciones.
- Task 6 deliberately keeps pinned tareas out of the paginated query. Merging them in would reintroduce the cursor fragility documented in the design-pass spec §2.8.
- The enrollment lookup in Task 5 has no status filter on purpose: ghost and polizón are in the class.
