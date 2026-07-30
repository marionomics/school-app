# Phase 2a — Tareas y el motor de calificación: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teachers can assign tareas, students can mark a reply as their entrega and see the lateness penalty before confirming, and the grade engine computes all four terms of the formula from real data.

**Architecture:** A new pure-function service `backend/app/services/grades.py` owns the entire formula and is the most-tested file in the repo. The `points_ledger` stays the append-only event log; the engine applies the maths on top of it. Three small Alembic migrations, each landing with the feature that uses it, so no commit ships dead schema.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, pytest (PostgreSQL in CI, SQLite locally), React + Vite + TanStack Query, vitest.

**Design spec (source of truth):** `docs/superpowers/specs/2026-07-30-phase-2a-tareas-y-motor-design.md`

## Global Constraints

- Scale is 0–100. "Una décima" (10-scale) = **1 point** (100-scale). One falta = **−10 points**, un punto entero.
- Default rubros sum to 60 (`tareas_weight` 30 + `examenes_weight` 30). **The missing ~40 is intentional.** Never make weights sum to 100, never warn that they don't.
- Lateness tiers: on time 100 · `<24h` 90 · `<7d` 50 · else 20. Boundaries closed at the top: exactly 24 h → 50, exactly 7 d → 20.
- Like points are concave: `like_value × N ^ like_exponent`, default exponent `0.5`. Participación taps stay linear.
- **Never sum `forum_like` row points.** The engine counts non-revoked rows and applies the curve.
- All grade arithmetic in `Decimal`. No float touches a grade. Round once, at the API boundary, 2 dp, `ROUND_HALF_UP`.
- Grades are computed, never stored. Veto = revocation flag, never DELETE.
- Only `active` enrollments earn or receive a grade. `ghost` 👻 and `polizon` 🥷 post freely, earn nothing.
- All user-facing copy is a placeholder in `frontend/src/strings/es.ts`. Mario writes final copy.
- Mobile-first: QA at 390 px before desktop.
- **Every commit must leave `main` deployable.** API response changes are additive until the consumer is updated in the same or an earlier commit.
- CI runs `pytest tests -v`, then applies migrations to PostgreSQL and asserts no model drift. All three must pass before a task is done.

---

### Task 1: `tarea` post type

**Files:**
- Modify: `backend/app/models.py` (Post class)
- Create: `backend/alembic/versions/<generated>_tarea_columns.py`
- Modify: `backend/app/services/dates.py` (create), `backend/app/routers/posts.py`, `backend/app/schemas.py`
- Test: `backend/tests/test_tareas.py` (create)

**Interfaces:**
- Consumes: existing `Post`, `create_post` router, teacher ownership check from Phase 1.
- Produces: `next_sunday_due(now: datetime, tz_name: str) -> datetime` in `app/services/dates.py`; `posts.due_date` and `posts.is_entrega` columns; `POST /api/posts` accepting `type="tarea"` with optional `due_date`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_tareas.py`:

```python
from datetime import datetime, timedelta, timezone

from app.services.dates import next_sunday_due


def test_next_sunday_from_wednesday():
    # Wed 2026-08-05 10:00 UTC -> Sunday 2026-08-09 23:59 local
    now = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)
    due = next_sunday_due(now, "America/Mexico_City")
    local = due.astimezone(timezone.utc)
    assert local > now
    assert (local - now) < timedelta(days=7)


def test_next_sunday_from_sunday_skips_to_following_week():
    # Sunday 2026-08-09 12:00 UTC must NOT return the same day
    now = datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc)
    due = next_sunday_due(now, "America/Mexico_City")
    assert (due - now) > timedelta(days=5)


def test_teacher_creates_tarea(client, teacher_headers, klass):
    r = client.post("/api/posts", data={
        "content": "Lee el capítulo 3 y resume",
        "type": "tarea",
        "class_id": str(klass.id),
    }, headers=teacher_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["type"] == "tarea"
    assert body["due_date"] is not None


def test_teacher_creates_tarea_with_explicit_due_date(client, teacher_headers, klass):
    due = datetime(2026, 9, 1, 23, 59, tzinfo=timezone.utc)
    r = client.post("/api/posts", data={
        "content": "Entrega el proyecto",
        "type": "tarea",
        "class_id": str(klass.id),
        "due_date": due.isoformat(),
    }, headers=teacher_headers)
    assert r.status_code == 201, r.text
    assert r.json()["due_date"].startswith("2026-09-01")


def test_student_cannot_create_tarea(client, auth_headers, klass):
    r = client.post("/api/posts", data={
        "content": "intento de tarea",
        "type": "tarea",
        "class_id": str(klass.id),
    }, headers=auth_headers)
    assert r.status_code == 403


def test_tarea_requires_class(client, teacher_headers):
    r = client.post("/api/posts", data={
        "content": "tarea sin clase",
        "type": "tarea",
    }, headers=teacher_headers)
    assert r.status_code == 422
```

No new fixtures needed. `backend/tests/conftest.py` already provides `teacher_headers`, `auth_headers` (the *student* one — note the name), `klass`, `enrolled`, `student2`, `student2_headers` and `ghost`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_tareas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.dates'`

- [ ] **Step 3: Add the date helper**

`backend/app/services/dates.py`:

```python
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def next_sunday_due(now: datetime, tz_name: str) -> datetime:
    """Next Sunday at 23:59 local time, returned in UTC.

    If `now` is already Sunday the result is the FOLLOWING Sunday — a tarea
    created on Sunday is never due the same night.
    """
    tz = ZoneInfo(tz_name)
    local = now.astimezone(tz)
    days_ahead = (6 - local.weekday()) % 7  # Monday=0 … Sunday=6
    if days_ahead == 0:
        days_ahead = 7
    due_local = (local + timedelta(days=days_ahead)).replace(
        hour=23, minute=59, second=0, microsecond=0
    )
    return due_local.astimezone(timezone.utc)
```

- [ ] **Step 4: Add the columns to the model**

In `backend/app/models.py`, inside `class Post`, after the `taps` column:

```python
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_entrega: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

Update the `type` comment on the same class to `# regular|participacion|tarea (examen en Fase 2b)`.

- [ ] **Step 5: Generate and review the migration**

```bash
cd backend
alembic revision --autogenerate -m "tarea columns on posts"
```

Open the generated file and confirm it contains exactly two `op.add_column` calls on `posts` and nothing else. Autogenerate sometimes emits spurious `alter_column` lines for existing columns — delete them if present.

Then apply and confirm no drift:

```bash
alembic upgrade head
```

- [ ] **Step 6: Accept the new fields in the router**

In `backend/app/routers/posts.py`, the `create_post` endpoint currently accepts `content`, `type`, `class_id`, `taps` and `files` as Form fields. Add `due_date` as an optional Form field, and add this validation immediately after the existing type validation:

```python
    if type == "tarea":
        if user.role != "teacher":
            raise HTTPException(status_code=403,
                                detail="Solo el profesor puede crear tareas")
        if class_id is None:
            raise HTTPException(status_code=422,
                                detail="Una tarea necesita una clase")
```

When building the `Post`, set:

```python
        due_date=(
            _parse_due_date(due_date)
            if due_date
            else next_sunday_due(utcnow(), settings.timezone)
        ) if type == "tarea" else None,
```

Add the parse helper near the top of the router module:

```python
def _parse_due_date(raw: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        raise HTTPException(status_code=422, detail="Fecha de entrega inválida")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
```

Import `next_sunday_due` from `app.services.dates` and `settings` from `app.config`.

- [ ] **Step 7: Expose the field in the schema**

In `backend/app/schemas.py`, add to the post-output model used by `serialize_post`:

```python
    due_date: Optional[datetime] = None
    is_entrega: bool = False
```

and include both in `serialize_post` in `backend/app/routers/posts.py`.

- [ ] **Step 8: Run the full suite and commit**

Run: `cd backend && pytest tests -v`
Expected: all previous tests plus the 6 new ones pass.

```bash
git add backend/
git commit -m "feat(backend): tarea post type with default Sunday due date"
```

---

### Task 2: "Es mi entrega" on replies

**Files:**
- Modify: `backend/app/routers/posts.py`
- Test: `backend/tests/test_entregas.py` (create)

**Interfaces:**
- Consumes: `posts.is_entrega` from Task 1.
- Produces: `POST /api/posts` replies accept `is_entrega: bool`; marking a new entrega clears the previous one for the same (student, tarea). No new functions.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_entregas.py`:

```python
from app.models import Post


def _tarea(client, teacher_headers, klass):
    r = client.post("/api/posts", data={
        "content": "Tarea 1", "type": "tarea", "class_id": str(klass.id),
    }, headers=teacher_headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_reply_can_be_marked_as_entrega(client, teacher_headers, auth_headers, klass, enrolled):
    tarea_id = _tarea(client, teacher_headers, klass)
    r = client.post("/api/posts", data={
        "content": "Aquí está mi tarea",
        "parent_id": str(tarea_id),
        "is_entrega": "true",
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    assert r.json()["is_entrega"] is True


def test_marking_second_entrega_clears_the_first(db, client, teacher_headers, auth_headers, klass, enrolled):
    tarea_id = _tarea(client, teacher_headers, klass)
    first = client.post("/api/posts", data={
        "content": "primera", "parent_id": str(tarea_id), "is_entrega": "true",
    }, headers=auth_headers).json()
    second = client.post("/api/posts", data={
        "content": "segunda", "parent_id": str(tarea_id), "is_entrega": "true",
    }, headers=auth_headers).json()

    db.expire_all()
    assert db.get(Post, first["id"]).is_entrega is False
    assert db.get(Post, second["id"]).is_entrega is True


def test_entrega_only_on_a_tarea(client, auth_headers, klass, enrolled, student):
    plain = client.post("/api/posts", data={
        "content": "post normal", "class_id": str(klass.id),
    }, headers=auth_headers).json()
    r = client.post("/api/posts", data={
        "content": "no debería contar", "parent_id": str(plain["id"]), "is_entrega": "true",
    }, headers=auth_headers)
    assert r.status_code == 422


def test_entrega_requires_active_enrollment(db, client, teacher_headers, klass, ghost):
    # `ghost` is enrolled with status="ghost": may post, earns nothing, cannot entregar.
    from app.auth.sessions import create_session
    headers = {"Authorization": f"Bearer {create_session(db, ghost)}"}
    tarea_id = _tarea(client, teacher_headers, klass)
    r = client.post("/api/posts", data={
        "content": "soy fantasma", "parent_id": str(tarea_id), "is_entrega": "true",
    }, headers=headers)
    assert r.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_entregas.py -v`
Expected: FAIL — replies ignore `is_entrega`, so `test_reply_can_be_marked_as_entrega` asserts `True is False`.

- [ ] **Step 3: Implement**

In `create_post` in `backend/app/routers/posts.py`, add `is_entrega: bool = Form(False)` to the signature. After the parent is resolved and validated, add:

```python
    entrega = False
    if is_entrega:
        if parent is None or parent.type not in ("tarea", "examen"):
            raise HTTPException(
                status_code=422,
                detail="Solo puedes marcar como entrega una respuesta a una tarea")
        active = (
            db.query(Enrollment)
            .filter(Enrollment.user_id == user.id,
                    Enrollment.class_id == parent.class_id,
                    Enrollment.status == "active")
            .first()
        )
        if active is None:
            raise HTTPException(
                status_code=403,
                detail="Necesitas estar inscrito en la clase para entregar")
        # Latest wins: clear any previous entrega by this student on this tarea.
        (db.query(Post)
           .filter(Post.author_id == user.id,
                   Post.parent_id == parent.id,
                   Post.is_entrega.is_(True))
           .update({"is_entrega": False}, synchronize_session=False))
        entrega = True
```

Set `is_entrega=entrega` when constructing the `Post`. Import `Enrollment` if not already imported.

- [ ] **Step 4: Run the full suite and commit**

Run: `cd backend && pytest tests -v`
Expected: all pass.

```bash
git add backend/
git commit -m "feat(backend): mark a reply as entrega, latest wins"
```

---

### Task 3: Grade engine — config, lateness and the tareas rubro

**Files:**
- Modify: `backend/app/models.py` (add `PointsConfig`, `Review`)
- Create: `backend/alembic/versions/<generated>_points_config_and_reviews.py`
- Create: `backend/app/services/grades.py`
- Modify: `backend/app/routers/classes.py` (create config row with the class), `backend/app/routers/grades.py`
- Test: `backend/tests/test_grades_engine.py` (create)

**Interfaces:**
- Consumes: `posts.due_date`, `posts.is_entrega`, `Enrollment`, `PointsLedger`.
- Produces:
  - `lateness_score(entrega_at: datetime, due_at: datetime) -> Decimal` returning one of `100/90/50/20`
  - `get_config(db, class_id) -> PointsConfig` — returns a defaults instance if no row exists, never `None`
  - `tareas_rubro(db, user_id, klass, now) -> Rubro`
  - `Rubro` dataclass: `evaluated: bool`, `points: Decimal`, `weight: int`, `count_due: int`, `count_entregadas: int`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_grades_engine.py`:

```python
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models import Post
from app.services.grades import lateness_score, get_config, tareas_rubro

DUE = datetime(2026, 8, 9, 23, 59, tzinfo=timezone.utc)


@pytest.mark.parametrize("delta,expected", [
    (timedelta(days=-3), Decimal("100")),
    (timedelta(0), Decimal("100")),
    (timedelta(hours=1), Decimal("90")),
    (timedelta(hours=23, minutes=59), Decimal("90")),
    (timedelta(hours=24), Decimal("50")),      # boundary: exactly 24h is NOT 90
    (timedelta(days=6), Decimal("50")),
    (timedelta(days=7), Decimal("20")),        # boundary: exactly 7d is NOT 50
    (timedelta(days=30), Decimal("20")),
])
def test_lateness_tiers_and_boundaries(delta, expected):
    assert lateness_score(DUE + delta, DUE) == expected


def test_config_falls_back_to_defaults_when_row_missing(db, klass):
    cfg = get_config(db, klass.id)
    assert cfg.tap_value == Decimal("1.0")
    assert cfg.like_value == Decimal("1.0")
    assert cfg.like_exponent == Decimal("0.5")


def _tarea(db, teacher, klass, due):
    p = Post(author_id=teacher.id, class_id=klass.id, type="tarea",
             content="t", due_date=due)
    db.add(p)
    db.commit()
    return p


def _entrega(db, student, tarea, at):
    p = Post(author_id=student.id, class_id=tarea.class_id, type="regular",
             parent_id=tarea.id, content="e", is_entrega=True, created_at=at)
    db.add(p)
    db.commit()
    return p


def test_no_tareas_due_is_unevaluated(db, student, teacher, klass, enrolled):
    _tarea(db, teacher, klass, DUE + timedelta(days=30))
    r = tareas_rubro(db, student.id, klass, now=DUE)
    assert r.evaluated is False
    assert r.points == Decimal("0")


def test_tarea_due_with_no_entrega_scores_zero_and_is_evaluated(db, student, teacher, klass, enrolled):
    _tarea(db, teacher, klass, DUE)
    r = tareas_rubro(db, student.id, klass, now=DUE + timedelta(days=1))
    assert r.evaluated is True          # distinct from the unevaluated case
    assert r.points == Decimal("0")
    assert r.count_due == 1
    assert r.count_entregadas == 0


def test_single_tarea_on_time_is_the_whole_weight(db, student, teacher, klass, enrolled):
    t = _tarea(db, teacher, klass, DUE)
    _entrega(db, student, t, DUE - timedelta(hours=2))
    r = tareas_rubro(db, student.id, klass, now=DUE + timedelta(days=1))
    assert r.points == Decimal("30")     # klass.tareas_weight default


def test_five_of_six_on_time(db, student, teacher, klass, enrolled):
    for i in range(5):
        t = _tarea(db, teacher, klass, DUE - timedelta(days=i))
        _entrega(db, student, t, t.due_date - timedelta(hours=1))
    _tarea(db, teacher, klass, DUE - timedelta(days=5))   # never handed in
    r = tareas_rubro(db, student.id, klass, now=DUE + timedelta(days=1))
    assert r.points == Decimal("25.00")


def test_latest_entrega_wins_even_when_worse(db, student, teacher, klass, enrolled):
    t = _tarea(db, teacher, klass, DUE)
    _entrega(db, student, t, DUE - timedelta(hours=1))          # on time
    late = _entrega(db, student, t, DUE + timedelta(hours=2))   # <24h late
    # simulate the router's latest-wins bookkeeping
    for p in db.query(Post).filter(Post.parent_id == t.id, Post.id != late.id):
        p.is_entrega = False
    db.commit()
    r = tareas_rubro(db, student.id, klass, now=DUE + timedelta(days=1))
    assert r.points == Decimal("27.00")   # 90% of 30


def test_deleted_entrega_falls_back_to_zero(db, student, teacher, klass, enrolled):
    t = _tarea(db, teacher, klass, DUE)
    e = _entrega(db, student, t, DUE - timedelta(hours=1))
    e.status = "deleted"
    db.commit()
    r = tareas_rubro(db, student.id, klass, now=DUE + timedelta(days=1))
    assert r.points == Decimal("0")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_grades_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.grades'`

- [ ] **Step 3: Add the two models**

In `backend/app/models.py`:

```python
class PointsConfig(Base):
    __tablename__ = "points_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), unique=True, index=True)
    tap_value: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("1.0"))
    like_value: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("1.0"))
    like_exponent: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.5"))
    like_cap: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    daily_post_limit: Mapped[int] = mapped_column(Integer, default=5)


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    entrega_post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), unique=True, index=True)
    reviewer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    # Scale follows the PARENT post type: 0–100 for a tarea, 1–10 for an examen.
    score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    auto_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 4: Generate the migration and backfill config rows**

```bash
cd backend
alembic revision --autogenerate -m "points_config and reviews"
```

In the generated file, after the two `create_table` calls, add a backfill so existing classes get a config row:

```python
    op.execute(
        "INSERT INTO points_config (class_id, tap_value, like_value, "
        "like_exponent, daily_post_limit) "
        "SELECT id, 1.0, 1.0, 0.5, 5 FROM classes"
    )
```

Apply it: `alembic upgrade head`

- [ ] **Step 5: Write the engine**

`backend/app/services/grades.py`:

```python
"""The grade engine. Pure functions over the ledger and the post tree.

Grades are computed, never stored. All arithmetic is Decimal — no float
ever touches a grade.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Class, PointsConfig, Post, Review

ON_TIME = Decimal("100")
UNDER_24H = Decimal("90")
UNDER_WEEK = Decimal("50")
LATE = Decimal("20")


@dataclass
class Rubro:
    evaluated: bool
    points: Decimal
    weight: int
    count_due: int = 0
    count_entregadas: int = 0


def lateness_score(entrega_at: datetime, due_at: datetime) -> Decimal:
    """Tier boundaries are closed at the top: exactly 24h -> 50, exactly 7d -> 20."""
    delta = entrega_at - due_at
    if delta <= timedelta(0):
        return ON_TIME
    if delta < timedelta(hours=24):
        return UNDER_24H
    if delta < timedelta(days=7):
        return UNDER_WEEK
    return LATE


def get_config(db: Session, class_id: int) -> PointsConfig:
    """Never returns None. A missing row must not be able to zero a grade."""
    cfg = db.query(PointsConfig).filter(PointsConfig.class_id == class_id).first()
    if cfg is not None:
        return cfg
    return PointsConfig(
        class_id=class_id,
        tap_value=Decimal("1.0"),
        like_value=Decimal("1.0"),
        like_exponent=Decimal("0.5"),
        like_cap=None,
        daily_post_limit=5,
    )


def _counting_entrega(db: Session, user_id: int, tarea_id: int) -> Optional[Post]:
    """Latest active entrega by this student on this tarea."""
    return (
        db.query(Post)
        .filter(Post.author_id == user_id,
                Post.parent_id == tarea_id,
                Post.is_entrega.is_(True),
                Post.status == "active")
        .order_by(Post.created_at.desc())
        .first()
    )


def tareas_rubro(db: Session, user_id: int, klass: Class, now: datetime) -> Rubro:
    due_tareas = (
        db.query(Post)
        .filter(Post.class_id == klass.id,
                Post.type == "tarea",
                Post.status == "active",
                Post.due_date.isnot(None),
                Post.due_date <= now)
        .all()
    )
    weight = klass.tareas_weight
    if not due_tareas:
        return Rubro(evaluated=False, points=Decimal("0"), weight=weight)

    total = Decimal("0")
    entregadas = 0
    for tarea in due_tareas:
        entrega = _counting_entrega(db, user_id, tarea.id)
        if entrega is None:
            continue
        entregadas += 1
        review = (
            db.query(Review)
            .filter(Review.entrega_post_id == entrega.id)
            .first()
        )
        if review is not None and review.score is not None:
            total += Decimal(review.score)          # already 0–100 for a tarea
        else:
            total += lateness_score(entrega.created_at, tarea.due_date)

    points = (total / len(due_tareas) / Decimal("100")) * weight
    return Rubro(evaluated=True, points=points, weight=weight,
                 count_due=len(due_tareas), count_entregadas=entregadas)
```

- [ ] **Step 6: Create a config row with every new class**

In `backend/app/routers/classes.py`, in the create-class endpoint, immediately after `db.add(klass)` and its `db.flush()`:

```python
    db.add(PointsConfig(class_id=klass.id))
```

Import `PointsConfig` from `app.models`.

- [ ] **Step 7: Surface the rubro on the grade endpoint (additively)**

In `backend/app/routers/grades.py`, inside `_summary`, keep every existing key exactly as it is and add:

```python
    from app.services.grades import tareas_rubro   # top-level import in practice

    tareas = tareas_rubro(db, user_id, klass, now=utcnow())
    summary["tareas"] = {
        "evaluated": tareas.evaluated,
        "points": float(round(tareas.points, 2)),
        "weight": tareas.weight,
        "count_due": tareas.count_due,
        "count_entregadas": tareas.count_entregadas,
    }
    summary["total"] = float(round(Decimal(str(summary["total"])) + tareas.points, 2))
```

The existing `counts` and `events` keys stay untouched so the deployed frontend keeps working.

- [ ] **Step 8: Run the full suite and commit**

Run: `cd backend && pytest tests -v`
Expected: all pass, including the 12 new engine tests.

```bash
git add backend/
git commit -m "feat(backend): grade engine with lateness scoring and the tareas rubro"
```

---

### Task 4: Grade engine — like curve, faltas and final assembly

**Files:**
- Modify: `backend/app/models.py` (add `ClassSession`, `AttendanceRecord`)
- Create: `backend/alembic/versions/<generated>_attendance_tables.py`
- Modify: `backend/app/services/grades.py`, `backend/app/routers/grades.py`
- Test: `backend/tests/test_grades_engine.py` (extend)

**Interfaces:**
- Consumes: `Rubro`, `get_config`, `tareas_rubro` from Task 3.
- Produces:
  - `like_points(n: int, like_value: Decimal, exponent: Decimal) -> Decimal`
  - `ledger_breakdown(db, user_id, class_id) -> dict` with keys `participaciones`, `likes`, `likes_count`, `other`
  - `faltas_breakdown(db, user_id, class_id) -> tuple[int, Decimal]`
  - `calculate_grade(db, user_id, klass, now) -> GradeBreakdown` with `tareas`, `examenes`, `ledger`, `faltas`, `total`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_grades_engine.py`:

```python
from decimal import Decimal

from app.models import AttendanceRecord, ClassSession, PointsLedger
from app.services.grades import (calculate_grade, faltas_breakdown,
                                 ledger_breakdown, like_points)


def test_like_curve_basic_values():
    one = Decimal("1.0")
    assert like_points(0, one, Decimal("0.5")) == Decimal("0")
    assert like_points(1, one, Decimal("0.5")) == Decimal("1")
    assert round(like_points(100, one, Decimal("0.5")), 2) == Decimal("10.00")
    assert round(like_points(10000, one, Decimal("0.5")), 2) == Decimal("100.00")


def test_exponent_one_reproduces_linear_exactly():
    one = Decimal("1.0")
    for n in (1, 7, 50, 999):
        assert round(like_points(n, one, Decimal("1.0")), 2) == Decimal(n)


def _like_row(db, user, klass, revoked=False):
    row = PointsLedger(user_id=user.id, class_id=klass.id,
                       source_type="forum_like", source_id=0,
                       points=Decimal("1.00"))
    if revoked:
        row.revoked_at = DUE
    db.add(row)
    db.commit()


def test_likes_are_counted_not_summed(db, student, klass, enrolled):
    for _ in range(9):
        _like_row(db, student, klass)
    out = ledger_breakdown(db, student.id, klass.id)
    assert out["likes_count"] == 9
    assert round(out["likes"], 2) == Decimal("3.00")     # sqrt(9), NOT 9


def test_revoked_likes_leave_the_count_exact(db, student, klass, enrolled):
    for _ in range(4):
        _like_row(db, student, klass)
    _like_row(db, student, klass, revoked=True)
    out = ledger_breakdown(db, student.id, klass.id)
    assert out["likes_count"] == 4
    assert round(out["likes"], 2) == Decimal("2.00")     # sqrt(4)


def test_participaciones_stay_linear(db, student, klass, enrolled):
    db.add(PointsLedger(user_id=student.id, class_id=klass.id,
                        source_type="participacion", source_id=1,
                        points=Decimal("3.00")))
    db.commit()
    out = ledger_breakdown(db, student.id, klass.id)
    assert out["participaciones"] == Decimal("3.00")


def test_faltas_cost_ten_each_and_ignore_approved_justifications(db, student, teacher, klass, enrolled):
    session = ClassSession(class_id=klass.id, date=DUE.date())
    db.add(session)
    db.flush()
    db.add(AttendanceRecord(session_id=session.id, user_id=student.id, status="absent"))
    db.add(AttendanceRecord(session_id=session.id, user_id=student.id, status="absent",
                            justification_status="approved"))
    db.add(AttendanceRecord(session_id=session.id, user_id=student.id, status="present"))
    db.commit()
    count, points = faltas_breakdown(db, student.id, klass.id)
    assert count == 1                      # the approved one does not count
    assert points == Decimal("10")


def test_full_grade_assembly_excludes_unevaluated_rubros(db, student, teacher, klass, enrolled):
    t = _tarea(db, teacher, klass, DUE)
    _entrega(db, student, t, DUE - timedelta(hours=1))
    for _ in range(9):
        _like_row(db, student, klass)

    g = calculate_grade(db, student.id, klass, now=DUE + timedelta(days=1))
    assert g.tareas.evaluated is True
    assert g.examenes.evaluated is False          # no exámenes exist yet
    assert round(g.total, 2) == Decimal("33.00")  # 30 tareas + sqrt(9) likes
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_grades_engine.py -v`
Expected: FAIL — `ImportError: cannot import name 'like_points'`

- [ ] **Step 3: Add the attendance models**

In `backend/app/models.py`:

```python
class ClassSession(Base):
    __tablename__ = "class_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("class_sessions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20))  # present|absent|late|excused
    justification_text: Mapped[Optional[str]] = mapped_column(Text)
    justification_file_key: Mapped[Optional[str]] = mapped_column(String(500))
    justification_status: Mapped[Optional[str]] = mapped_column(String(20))  # pending|approved|rejected
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
```

Generate and apply the migration:

```bash
cd backend
alembic revision --autogenerate -m "attendance tables"
alembic upgrade head
```

- [ ] **Step 4: Implement the remaining engine pieces**

Append to `backend/app/services/grades.py`:

```python
FALTA_COST = Decimal("10")


def like_points(n: int, like_value: Decimal, exponent: Decimal) -> Decimal:
    """Concave by default: the nth like is worth sqrt(n) - sqrt(n-1), not 1.

    NEVER sum the points column of forum_like ledger rows — those rows are the
    event log. This function is the only source of like points.
    """
    if n <= 0:
        return Decimal("0")
    exponent = Decimal(exponent)
    if exponent == Decimal("1"):
        base = Decimal(n)
    elif exponent == Decimal("0.5"):
        base = Decimal(n).sqrt()
    else:
        base = (Decimal(n).ln() * exponent).exp()
    return Decimal(like_value) * base


def ledger_breakdown(db: Session, user_id: int, class_id: int) -> dict:
    rows = (
        db.query(PointsLedger)
        .filter(PointsLedger.user_id == user_id,
                PointsLedger.class_id == class_id,
                PointsLedger.revoked_at.is_(None))
        .all()
    )
    cfg = get_config(db, class_id)
    participaciones = sum((r.points for r in rows if r.source_type == "participacion"),
                          Decimal("0"))
    likes_count = sum(1 for r in rows if r.source_type == "forum_like")
    other = sum((r.points for r in rows
                 if r.source_type not in ("participacion", "forum_like")),
                Decimal("0"))
    return {
        "participaciones": participaciones,
        "likes": like_points(likes_count, cfg.like_value, cfg.like_exponent),
        "likes_count": likes_count,
        "other": other,
    }


def faltas_breakdown(db: Session, user_id: int, class_id: int) -> tuple[int, Decimal]:
    """Unjustified absences only.

    The NULL case is spelled out: `!= 'approved'` alone silently drops NULL
    rows in SQL, and justification_status is nullable.
    """
    count = (
        db.query(AttendanceRecord)
        .join(ClassSession, AttendanceRecord.session_id == ClassSession.id)
        .filter(ClassSession.class_id == class_id,
                AttendanceRecord.user_id == user_id,
                AttendanceRecord.status == "absent",
                or_(AttendanceRecord.justification_status.is_(None),
                    AttendanceRecord.justification_status != "approved"))
        .count()
    )
    return count, Decimal(count) * FALTA_COST


@dataclass
class GradeBreakdown:
    tareas: Rubro
    examenes: Rubro
    ledger: dict
    faltas_count: int
    faltas_points: Decimal
    total: Decimal


def examenes_rubro(db: Session, user_id: int, klass: Class, now: datetime) -> Rubro:
    """Exámenes are created in Phase 2b; until then this is always unevaluated.

    The logic is written and tested now so the engine is finished in one pass.
    """
    closed = (
        db.query(Post)
        .filter(Post.class_id == klass.id,
                Post.type == "examen",
                Post.status == "active",
                Post.due_date.isnot(None),
                Post.due_date <= now)
        .all()
    )
    weight = klass.examenes_weight
    if not closed:
        return Rubro(evaluated=False, points=Decimal("0"), weight=weight)

    total = Decimal("0")
    entregadas = 0
    for examen in closed:
        entrega = _counting_entrega(db, user_id, examen.id)
        if entrega is None:
            continue
        entregadas += 1
        review = db.query(Review).filter(Review.entrega_post_id == entrega.id).first()
        if review is not None and review.score is not None:
            total += Decimal(review.score) / Decimal("10")   # 1–10 scale
    points = (total / len(closed)) * weight
    return Rubro(evaluated=True, points=points, weight=weight,
                 count_due=len(closed), count_entregadas=entregadas)


def calculate_grade(db: Session, user_id: int, klass: Class,
                    now: datetime) -> GradeBreakdown:
    tareas = tareas_rubro(db, user_id, klass, now)
    examenes = examenes_rubro(db, user_id, klass, now)
    ledger = ledger_breakdown(db, user_id, klass.id)
    faltas_count, faltas_points = faltas_breakdown(db, user_id, klass.id)

    total = Decimal("0")
    if tareas.evaluated:
        total += tareas.points
    if examenes.evaluated:
        total += examenes.points
    total += ledger["participaciones"] + ledger["likes"] + ledger["other"]
    total -= faltas_points

    return GradeBreakdown(tareas=tareas, examenes=examenes, ledger=ledger,
                          faltas_count=faltas_count, faltas_points=faltas_points,
                          total=total)
```

Add the imports this needs at the top of the file: `from sqlalchemy import or_` and extend the models import to `AttendanceRecord, Class, ClassSession, PointsConfig, PointsLedger, Post, Review`.

- [ ] **Step 5: Rewrite `_summary` on top of the engine**

Replace the body of `_summary` in `backend/app/routers/grades.py` with a call to `calculate_grade`, keeping the legacy `counts` key so the currently deployed frontend does not break:

```python
def _summary(db: Session, user_id: int, klass: Class) -> dict:
    g = calculate_grade(db, user_id, klass, now=utcnow())
    rows = (
        db.query(PointsLedger)
        .filter(PointsLedger.user_id == user_id,
                PointsLedger.class_id == klass.id,
                PointsLedger.revoked_at.is_(None))
        .order_by(PointsLedger.created_at.desc())
        .all()
    )
    return {
        "class_id": klass.id,
        "class_name": klass.name,
        "total": _r(g.total),
        # legacy key, still read by the deployed frontend; removed in Task 9
        "counts": {
            "participaciones": sum(1 for r in rows if r.source_type == "participacion"),
            "likes_received": g.ledger["likes_count"],
        },
        "tareas": _rubro_json(g.tareas),
        "examenes": _rubro_json(g.examenes),
        "ledger": {
            "participaciones": _r(g.ledger["participaciones"]),
            "likes": _r(g.ledger["likes"]),
            "likes_count": g.ledger["likes_count"],
            "other": _r(g.ledger["other"]),
        },
        "faltas": {"count": g.faltas_count, "points": _r(g.faltas_points)},
        "events": [
            {"source_type": r.source_type, "points": float(r.points),
             "note": r.note, "created_at": r.created_at}
            for r in rows[:50]
        ],
    }


def _r(value: Decimal) -> float:
    return float(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _rubro_json(r) -> dict:
    return {"evaluated": r.evaluated, "points": _r(r.points), "weight": r.weight,
            "count_due": r.count_due, "count_entregadas": r.count_entregadas}
```

Import `ROUND_HALF_UP` from `decimal` and `calculate_grade` from `app.services.grades`.

- [ ] **Step 6: Run the full suite and commit**

Run: `cd backend && pytest tests -v`
Expected: all pass.

```bash
git add backend/
git commit -m "feat(backend): concave like points, faltas term, full grade assembly"
```

---

### Task 5: Frontend types and the lateness preview

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Create: `frontend/src/lib/lateness.ts`, `frontend/src/lib/lateness.test.ts`

**Interfaces:**
- Produces: `latenessTier(entregaAt: Date, dueAt: Date) -> { pct: number; key: "onTime" | "under24h" | "underWeek" | "late" }`; extended `Post` and `GradeSummary` types.

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/lateness.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { latenessTier } from "./lateness";

const DUE = new Date("2026-08-09T23:59:00Z");
const at = (ms: number) => new Date(DUE.getTime() + ms);
const HOUR = 3600_000;
const DAY = 24 * HOUR;

describe("latenessTier", () => {
  it("on time before and exactly at the deadline", () => {
    expect(latenessTier(at(-DAY), DUE).pct).toBe(100);
    expect(latenessTier(at(0), DUE).pct).toBe(100);
  });

  it("under 24h is 90", () => {
    expect(latenessTier(at(HOUR), DUE).pct).toBe(90);
    expect(latenessTier(at(23 * HOUR), DUE).pct).toBe(90);
  });

  it("exactly 24h is already 50", () => {
    expect(latenessTier(at(24 * HOUR), DUE).pct).toBe(50);
  });

  it("exactly 7 days is already 20", () => {
    expect(latenessTier(at(7 * DAY), DUE).pct).toBe(20);
    expect(latenessTier(at(30 * DAY), DUE).pct).toBe(20);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- --run`
Expected: FAIL — cannot resolve `./lateness`.

- [ ] **Step 3: Implement**

`frontend/src/lib/lateness.ts`:

```ts
export type LatenessKey = "onTime" | "under24h" | "underWeek" | "late";

const HOUR = 3600_000;
const DAY = 24 * HOUR;

/** Mirrors backend lateness_score. Boundaries closed at the top:
 *  exactly 24h is 50, exactly 7 days is 20. */
export function latenessTier(
  entregaAt: Date,
  dueAt: Date,
): { pct: number; key: LatenessKey } {
  const delta = entregaAt.getTime() - dueAt.getTime();
  if (delta <= 0) return { pct: 100, key: "onTime" };
  if (delta < DAY) return { pct: 90, key: "under24h" };
  if (delta < 7 * DAY) return { pct: 50, key: "underWeek" };
  return { pct: 20, key: "late" };
}
```

- [ ] **Step 4: Extend the types**

In `frontend/src/lib/types.ts`, add to `Post`:

```ts
  due_date: string | null;
  is_entrega: boolean;
```

and add the new grade shapes, keeping `counts` for now:

```ts
export interface Rubro {
  evaluated: boolean;
  points: number;
  weight: number;
  count_due: number;
  count_entregadas: number;
}

export interface LedgerBreakdown {
  participaciones: number;
  likes: number;
  likes_count: number;
  other: number;
}
```

and inside `GradeSummary`:

```ts
  tareas: Rubro;
  examenes: Rubro;
  ledger: LedgerBreakdown;
  faltas: { count: number; points: number };
```

- [ ] **Step 5: Verify and commit**

Run: `cd frontend && npm test -- --run && npm run build && npm run lint`
Expected: 11 vitest tests pass (7 existing + 4 new), build and lint clean.

```bash
git add frontend/
git commit -m "feat(frontend): lateness preview helper and Phase 2a types"
```

---

### Task 6: Composer — tarea mode for teachers

**Files:**
- Modify: `frontend/src/pages/Compose.tsx`, `frontend/src/strings/es.ts`

**Interfaces:**
- Consumes: `POST /api/posts` with `type=tarea` and optional `due_date` (Task 1).

- [ ] **Step 1: Add the strings**

In `frontend/src/strings/es.ts`, inside `compose`:

```ts
    modeTarea: "Tarea",
    dueLabel: "Entrega",
    dueHint: "Por defecto: el próximo domingo",
    tareaPlaceholder: "¿Qué deben hacer y para cuándo?",
```

- [ ] **Step 2: Add the teacher mode**

In `frontend/src/pages/Compose.tsx`, widen the mode state:

```tsx
const [mode, setMode] = useState<"regular" | "participacion" | "tarea">("regular");
const [dueDate, setDueDate] = useState<string>("");
```

The student selector stays exactly as it is. Add a teacher-only selector beside it:

```tsx
      {!isStudent && (
        <div className="flex gap-2">
          {(["regular", "tarea"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`rounded-full px-3 py-1 text-sm ${mode === m ? "bg-primary text-primary-foreground" : "border"}`}
            >
              {m === "regular" ? es.compose.modeRegular : `📌 ${es.compose.modeTarea}`}
            </button>
          ))}
        </div>
      )}

      {mode === "tarea" && (
        <label className="text-sm">
          {es.compose.dueLabel}
          <input
            type="datetime-local"
            className="ml-2 rounded-md border px-2 py-1"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
          />
          <span className="ml-2 text-xs text-muted-foreground">{es.compose.dueHint}</span>
        </label>
      )}
```

In the mutation, send the type and the optional due date:

```tsx
      fd.set("type", mode === "participacion" ? "participacion" : mode);
      if (mode === "tarea" && dueDate) {
        fd.set("due_date", new Date(dueDate).toISOString());
      }
```

Leaving the date empty must send nothing, so the server applies next-Sunday.

Use `es.compose.tareaPlaceholder` for the textarea when `mode === "tarea"`.

- [ ] **Step 3: Verify and commit**

Run: `cd frontend && npm test -- --run && npm run build && npm run lint`

Manual at 390 px: as teacher, the Tarea chip appears and the date control shows; as student it does not. Publishing a tarea with an empty date returns a post whose `due_date` is the coming Sunday.

```bash
git add frontend/
git commit -m "feat(frontend): teachers can assign tareas from the composer"
```

---

### Task 7: Entrega toggle with penalty preview

**Files:**
- Modify: `frontend/src/pages/Thread.tsx`, `frontend/src/strings/es.ts`

**Interfaces:**
- Consumes: `latenessTier` (Task 5), `POST /api/posts` with `is_entrega` (Task 2).

- [ ] **Step 1: Add the strings**

In `frontend/src/strings/es.ts`, inside `post`:

```ts
    entregaToggle: "Es mi entrega",
    entregaOnTime: "Entrega a tiempo · 100%",
    entregaUnder24h: "Con retraso · 90%",
    entregaUnderWeek: "Con retraso · 50%",
    entregaLate: "Muy atrasada · 20%",
    entregaReplaces: "Reemplaza tu entrega anterior",
```

- [ ] **Step 2: Wire the toggle into the reply composer**

In `frontend/src/pages/Thread.tsx`, where the reply composer lives, add state and render the toggle only when the root post is a tarea:

```tsx
const [isEntrega, setIsEntrega] = useState(false);

const tierLabel = (() => {
  if (!post?.due_date) return null;
  const { key } = latenessTier(new Date(), new Date(post.due_date));
  return {
    onTime: es.post.entregaOnTime,
    under24h: es.post.entregaUnder24h,
    underWeek: es.post.entregaUnderWeek,
    late: es.post.entregaLate,
  }[key];
})();
```

```tsx
{post?.type === "tarea" && (
  <div className="flex flex-col gap-1">
    <label className="flex items-center gap-2 text-sm">
      <input
        type="checkbox"
        checked={isEntrega}
        onChange={(e) => setIsEntrega(e.target.checked)}
      />
      {es.post.entregaToggle}
    </label>
    {isEntrega && tierLabel && (
      <p className="text-xs text-muted-foreground">{tierLabel}</p>
    )}
  </div>
)}
```

Send it with the reply and reset it after a successful submit:

```tsx
      if (isEntrega) fd.set("is_entrega", "true");
```

Import `latenessTier` from `@/lib/lateness`.

- [ ] **Step 3: Verify and commit**

Run: `cd frontend && npm test -- --run && npm run build && npm run lint`

Manual at 390 px: on a tarea thread the toggle appears; enabling it shows the tier; on a regular post it never appears. Submitting marks the reply and the grade chip moves after invalidation.

```bash
git add frontend/
git commit -m "feat(frontend): entrega toggle with lateness preview"
```

---

### Task 8: Badges and the rubros breakdown

**Files:**
- Modify: `frontend/src/components/PostCard.tsx`, `frontend/src/components/GradeChip.tsx`, `frontend/src/strings/es.ts`

**Interfaces:**
- Consumes: `Post.due_date`, `Post.is_entrega`, `GradeSummary.tareas/examenes/ledger/faltas`.

- [ ] **Step 1: Add the strings**

```ts
  // inside feed
  tareaBadge: "Tarea",
  entregaBadge: "Entrega",
  dueOn: "Entrega {date}",
  // inside grade
  tareas: "Tareas",
  examenes: "Exámenes",
  notEvaluated: "—",
  noTareasYet: "sin tareas asignadas aún",
  noExamenesYet: "sin exámenes aún",
  faltas: "Faltas",
  likesWithCount: "{n} likes",
```

- [ ] **Step 2: Badges in PostCard**

In `frontend/src/components/PostCard.tsx`, next to the existing type badge logic:

```tsx
{post.type === "tarea" && (
  <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-700">
    📌 {es.feed.tareaBadge}
    {post.due_date && ` · ${es.feed.dueOn.replace(
      "{date}", new Date(post.due_date).toLocaleDateString("es-MX"))}`}
  </span>
)}
{post.is_entrega && (
  <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs font-medium text-emerald-700">
    ✅ {es.feed.entregaBadge}
  </span>
)}
```

- [ ] **Step 3: Rubros in GradeChip**

In `frontend/src/components/GradeChip.tsx`, replace the `dl` block that currently reads `g.counts` with:

```tsx
<dl className="mt-2 space-y-1 text-sm">
  <div className="flex justify-between">
    <dt>📌 {es.grade.tareas}</dt>
    <dd>
      {g.tareas.evaluated
        ? `${g.tareas.points} / ${g.tareas.weight}`
        : `${es.grade.notEvaluated}  ${es.grade.noTareasYet}`}
    </dd>
  </div>
  <div className="flex justify-between">
    <dt>📝 {es.grade.examenes}</dt>
    <dd>
      {g.examenes.evaluated
        ? `${g.examenes.points} / ${g.examenes.weight}`
        : `${es.grade.notEvaluated}  ${es.grade.noExamenesYet}`}
    </dd>
  </div>
  <div className="flex justify-between">
    <dt>🗣️ {es.grade.participaciones}</dt>
    <dd>{g.ledger.participaciones}</dd>
  </div>
  <div className="flex justify-between">
    <dt>♥ {es.grade.likes}</dt>
    <dd>
      {g.ledger.likes} · {es.grade.likesWithCount.replace("{n}", String(g.ledger.likes_count))}
    </dd>
  </div>
  {g.faltas.count > 0 && (
    <div className="flex justify-between text-destructive">
      <dt>🚫 {es.grade.faltas}</dt>
      <dd>−{g.faltas.points}</dd>
    </div>
  )}
</dl>
```

Showing `likes` next to `likes_count` is deliberate: with the concave curve, "18 likes → 4.24 pts" is otherwise mysterious.

- [ ] **Step 4: Verify and commit**

Run: `cd frontend && npm test -- --run && npm run build && npm run lint`

Manual at 390 px: a fresh student sees `—` for both rubros; after one on-time entrega Tareas reads `30 / 30`.

```bash
git add frontend/
git commit -m "feat(frontend): tarea/entrega badges and rubros in the grade breakdown"
```

---

### Task 9: Drop the legacy key and close out the docs

**Files:**
- Modify: `backend/app/routers/grades.py`, `frontend/src/lib/types.ts`, `planning/roadmap.md`, `planning/changelog.md`

**Interfaces:**
- Removes: the legacy `counts` key from the grade payload. Safe only because Task 8 stopped reading it.

- [ ] **Step 1: Remove the legacy key**

Delete the `"counts"` entry from `_summary` in `backend/app/routers/grades.py` and the `counts` field from `GradeSummary` in `frontend/src/lib/types.ts`.

- [ ] **Step 2: Confirm nothing still reads it**

Run: `grep -rn "counts" frontend/src backend/app backend/tests`
Expected: no hits referring to the grade payload. Fix any test that still asserts on it.

- [ ] **Step 3: Update the docs**

In `planning/roadmap.md`, under Fase 2, check off the items 2a delivered:

```
- [x] Posts tipo tarea (solo teacher; tarea default domingo) — examen en 2b
- [x] Toggle "Es mi entrega" en replies + preview de penalización
- [x] Auto-score por lateness (100/90/50/20) — override del profe en 2b
- [x] Motor de calificación completo (rubros + ledger + faltas) con tests
```

Add a dated entry to `planning/changelog.md` covering: tareas with default Sunday due dates, entregas with latest-wins, the lateness auto-score, the concave like curve replacing linear, the faltas term landing before any attendance UI exists, and what remains for 2b.

- [ ] **Step 4: Full verification and commit**

Run: `cd backend && pytest tests -v` — Expected: all pass.
Run: `cd frontend && npm test -- --run && npm run build && npm run lint` — Expected: clean.

```bash
git add backend/ frontend/ planning/
git commit -m "chore: drop legacy grade payload key, close out Phase 2a docs"
```

---

## Self-Review Notes

**Spec coverage.** §2.1 tareas denominator → Task 3 (`tareas_rubro` filters `due_date <= now`, unevaluated vs zero split across two tests) · §2.2 live vs final → Task 4 (`calculate_grade` excludes unevaluated rubros; the end-of-course gift is display-side and lands with 2b's class settings, noted below) · §2.3 concave likes → Task 4 (`like_points`, config in Task 3) · §2.4 ledger as event log → Task 4 (`ledger_breakdown` counts, never sums) · §2.5 latest wins → Task 2 (router) and Task 3 (`_counting_entrega`) · §3 data model → Tasks 1, 3, 4 (three migrations, each with its feature) · §4 engine → Tasks 3–4 · §5 API → Tasks 1, 2, 3, 4 · §6 frontend → Tasks 5–8 · §7 testing → Tasks 3–5.

**Known gap, deliberately deferred.** The spec's *final* grade rule (a rubro unevaluated at `end_date` awards full weight) is **not** implemented in 2a. Nothing in 2a reads `end_date`, and the rule only ever fires after a course ends — which cannot happen before 2b ships. Implementing it now would mean writing an untestable-in-practice branch months before it matters. It is listed as the first item for 2b.

**Type consistency.** `Rubro` fields (`evaluated`, `points`, `weight`, `count_due`, `count_entregadas`) match between the dataclass (Task 3), `_rubro_json` (Task 4), and the TS interface (Task 5). `ledger_breakdown` keys (`participaciones`, `likes`, `likes_count`, `other`) match `LedgerBreakdown` in TS. `latenessTier` returns the same four tiers as `lateness_score`, with identical boundary directions, verified by parallel test suites.

**Deliberate ordering.** Every API shape change is additive until Task 8 updates the consumer, and only Task 9 removes the legacy key — so each commit can be deployed to Railway without breaking the running frontend.

## Notes for 2b

- Final-grade gift rule at `end_date` (see gap above)
- `examen` post type, entrega window, 1–10 scoring — `examenes_rubro` already reads it
- Teacher override writing the first `reviews` rows; grading from the feed and from `Revisar`
- `Revisar`: entregas grouped by tarea, participaciones with one-tap veto
- `incentives` table, CRUD, awarding — `ledger_breakdown`'s `other` bucket already sums them
- Class settings UI: weights, `tap_value`, `like_value`, `like_exponent`
