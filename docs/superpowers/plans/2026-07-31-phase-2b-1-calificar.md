# Phase 2b-1 — Calificar: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the teacher a complete grading loop — exámenes on paper or digital, score overrides with feedback, a Revisar queue, and one-tap veto — without ever showing a student a zero for work nobody has graded yet.

**Architecture:** `reviews` is re-keyed on (item, student) so a paper examen can carry a score with no entrega. One write endpoint (`PUT /api/reviews`) serves both Revisar and inline feed grading. An examen enters the grade only when the teacher flips `graded_at`; a tarea keeps counting from its due date on the lateness auto-score. Scores stay private to their author, enforced in the serializer.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 typed `Mapped[]` columns, Alembic, pytest; React + Vite + TanStack Query + Tailwind + shadcn, vitest.

## Global Constraints

- Source of truth: `docs/superpowers/specs/2026-07-31-phase-2b-1-calificar-design.md`. Where this plan and the spec disagree, the spec wins.
- Every commit leaves `main` deployable and does something observable. A migration ships with the endpoint that exercises it.
- Grades are computed, never stored. All grade arithmetic is `Decimal`; the only rounding is `round_grade` at the API boundary in `backend/app/routers/grades.py`.
- `backend/app/services/points.py` stays the only module that writes `points_ledger` rows. Veto revokes via flag; never DELETE a ledger row.
- Scales: a tarea review is **0–100**, an examen review is **1–10**. Never mix them.
- Mobile-first. Phone gets a single column, large tap targets, `inputMode="numeric"`; laptop widens tabs into tables.
- All user-facing copy is a placeholder in `frontend/src/strings/es.ts`. Mario writes final copy. Never inline a Spanish string in a component.
- Run backend tests with `../venv/bin/python -m pytest` from `backend/` (the repo venv is Python 3.9 at `venv/`; the system `python3` has an incompatible SQLAlchemy).
- Default rubro weights are Tareas 30 + Exámenes 30 = 60. The missing 40 is intentional. Never make weights sum to 100, never warn that they don't.

---

### Task 1: Schema — examen columns, veto reason, reviews re-keyed

**Files:**
- Modify: `backend/app/models.py` (`Post`, `Review`)
- Create: `backend/alembic/versions/<generated>_examen_columns_and_reviews_rekey.py`
- Test: `backend/tests/test_migrations.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Post.examen_mode: Optional[str]`, `Post.graded_at: Optional[datetime]`, `Post.veto_reason: Optional[str]`; `Review(item_post_id: int, student_id: int, entrega_post_id: Optional[int], score: Optional[Decimal], auto_score: Optional[Decimal], feedback: Optional[str], reviewer_id: Optional[int], created_at, updated_at)` with `UNIQUE (item_post_id, student_id)`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_migrations.py`:

```python
def test_reviews_is_keyed_on_item_and_student(db):
    from sqlalchemy import inspect

    cols = {c["name"] for c in inspect(db.bind).get_columns("reviews")}
    assert {"item_post_id", "student_id", "entrega_post_id"} <= cols
    uniques = inspect(db.bind).get_unique_constraints("reviews")
    indexes = inspect(db.bind).get_indexes("reviews")
    keyed = [u["column_names"] for u in uniques] + \
            [i["column_names"] for i in indexes if i.get("unique")]
    assert ["item_post_id", "student_id"] in keyed


def test_posts_has_examen_and_veto_columns(db):
    from sqlalchemy import inspect

    cols = {c["name"] for c in inspect(db.bind).get_columns("posts")}
    assert {"examen_mode", "graded_at", "veto_reason"} <= cols
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_migrations.py -v`
Expected: FAIL — `item_post_id` not in the reviews columns.

- [ ] **Step 3: Update the models**

In `backend/app/models.py`, add to `Post` right after `is_entrega`:

```python
    examen_mode: Mapped[Optional[str]] = mapped_column(String(10))   # paper|digital, examen only
    graded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    veto_reason: Mapped[Optional[str]] = mapped_column(Text)
```

Replace the whole `Review` class with:

```python
class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("item_post_id", "student_id",
                                       name="uq_review_item_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # The tarea or examen being graded — NOT the entrega.
    item_post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Which submission this score was written against. NULL for a paper examen.
    entrega_post_id: Mapped[Optional[int]] = mapped_column(ForeignKey("posts.id"))
    reviewer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    # Scale follows the item type: 0–100 for a tarea, 1–10 for an examen.
    score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    auto_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
```

Add `UniqueConstraint` to the `sqlalchemy` import line at the top of the file.

- [ ] **Step 4: Generate the migration**

Run: `cd backend && ../venv/bin/python -m alembic revision --autogenerate -m "examen columns and reviews rekey"`

Open the generated file. Autogenerate will emit an `ALTER`-style diff for `reviews`; replace the reviews portion with a drop-and-recreate, because the table shipped empty in 2a and there is nothing to preserve:

```python
def upgrade() -> None:
    op.add_column('posts', sa.Column('examen_mode', sa.String(length=10), nullable=True))
    op.add_column('posts', sa.Column('graded_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('posts', sa.Column('veto_reason', sa.Text(), nullable=True))

    # reviews shipped empty in 2a — no rows to preserve, so re-key by rebuild.
    op.drop_index(op.f('ix_reviews_entrega_post_id'), table_name='reviews')
    op.drop_table('reviews')
    op.create_table(
        'reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('item_post_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('entrega_post_id', sa.Integer(), nullable=True),
        sa.Column('reviewer_id', sa.Integer(), nullable=True),
        sa.Column('score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('auto_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['item_post_id'], ['posts.id'], ),
        sa.ForeignKeyConstraint(['entrega_post_id'], ['posts.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('item_post_id', 'student_id', name='uq_review_item_student'),
    )
    op.create_index(op.f('ix_reviews_item_post_id'), 'reviews', ['item_post_id'])
    op.create_index(op.f('ix_reviews_student_id'), 'reviews', ['student_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_reviews_student_id'), table_name='reviews')
    op.drop_index(op.f('ix_reviews_item_post_id'), table_name='reviews')
    op.drop_table('reviews')
    op.create_table(
        'reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entrega_post_id', sa.Integer(), nullable=False),
        sa.Column('reviewer_id', sa.Integer(), nullable=True),
        sa.Column('score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('auto_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['entrega_post_id'], ['posts.id'], ),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reviews_entrega_post_id'), 'reviews', ['entrega_post_id'], unique=True)
    op.drop_column('posts', 'veto_reason')
    op.drop_column('posts', 'graded_at')
    op.drop_column('posts', 'examen_mode')
```

- [ ] **Step 5: Run the full suite**

Run: `cd backend && ../venv/bin/python -m pytest -q`
Expected: PASS — the two new tests included. The 2a drift test in `test_migrations.py` must still pass, proving models and migrations agree.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/alembic/versions backend/tests/test_migrations.py
git commit -m "feat(backend): examen columns, veto reason, reviews keyed on item+student"
```

---

### Task 2: Engine — reviews found by (item, student), with staleness

**Files:**
- Modify: `backend/app/services/grades.py`
- Test: `backend/tests/test_grades_engine.py`

**Interfaces:**
- Consumes: `Review` from Task 1.
- Produces: `counting_review(db, item_post_id: int, student_id: int, entrega: Optional[Post]) -> Optional[Review]` — returns the review only when it is not stale.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_grades_engine.py`:

```python
from app.models import Review
from app.services.grades import counting_review


def _review(db, teacher, item, student, entrega, score):
    r = Review(item_post_id=item.id, student_id=student.id,
               entrega_post_id=entrega.id if entrega else None,
               reviewer_id=teacher.id, score=Decimal(score))
    db.add(r)
    db.commit()
    return r


def test_review_overrides_the_lateness_auto_score(db, student, teacher, klass, enrolled):
    t = _tarea(db, teacher, klass, DUE)
    e = _entrega(db, student, t, DUE + timedelta(days=2))   # auto-score would be 50
    _review(db, teacher, t, student, e, "80")
    r = tareas_rubro(db, student.id, klass, now=DUE + timedelta(days=3))
    assert r.points == Decimal("80") / Decimal("100") * klass.tareas_weight


def test_review_written_against_a_replaced_entrega_is_ignored(db, student, teacher, klass, enrolled):
    t = _tarea(db, teacher, klass, DUE)
    first = _entrega(db, student, t, DUE - timedelta(hours=1))
    _review(db, teacher, t, student, first, "100")
    first.is_entrega = False                      # latest-wins cleared it
    second = _entrega(db, student, t, DUE + timedelta(days=2))
    db.commit()
    r = tareas_rubro(db, student.id, klass, now=DUE + timedelta(days=3))
    # stale review ignored -> falls back to the auto-score of the NEW entrega (50)
    assert r.points == Decimal("50") / Decimal("100") * klass.tareas_weight
    assert counting_review(db, t.id, student.id, second) is None


def test_review_with_null_score_falls_back_to_auto_score(db, student, teacher, klass, enrolled):
    t = _tarea(db, teacher, klass, DUE)
    e = _entrega(db, student, t, DUE - timedelta(hours=1))
    db.add(Review(item_post_id=t.id, student_id=student.id, entrega_post_id=e.id,
                  reviewer_id=teacher.id, feedback="buen intento"))
    db.commit()
    r = tareas_rubro(db, student.id, klass, now=DUE + timedelta(days=1))
    assert r.points == klass.tareas_weight        # on time, 100%
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_grades_engine.py -k review -v`
Expected: FAIL — `cannot import name 'counting_review'`.

- [ ] **Step 3: Implement**

In `backend/app/services/grades.py`, add after `_counting_entrega`:

```python
def counting_review(db: Session, item_post_id: int, student_id: int,
                    entrega: Optional[Post]) -> Optional[Review]:
    """The review for this (item, student), unless it is stale.

    A review is stale when it was written against a submission the student has
    since replaced — grading someone early must not freeze their score against
    work that no longer exists. A paper examen has no entrega and never goes
    stale.
    """
    review = (
        db.query(Review)
        .filter(Review.item_post_id == item_post_id,
                Review.student_id == student_id)
        .first()
    )
    if review is None:
        return None
    if review.entrega_post_id is None:
        return review
    if entrega is None or review.entrega_post_id != entrega.id:
        return None
    return review
```

In `tareas_rubro`, replace the review lookup block:

```python
        review = counting_review(db, tarea.id, user_id, entrega)
        if review is not None and review.score is not None:
            total += Decimal(review.score)          # already 0–100 for a tarea
        else:
            total += lateness_score(entrega.created_at, tarea.due_date)
```

- [ ] **Step 4: Run the full suite**

Run: `cd backend && ../venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/grades.py backend/tests/test_grades_engine.py
git commit -m "feat(backend): reviews keyed on item+student, stale reviews ignored"
```

---

### Task 3: Engine — exámenes gated on `graded_at`

**Files:**
- Modify: `backend/app/services/grades.py` (`examenes_rubro`)
- Test: `backend/tests/test_grades_engine.py`

**Interfaces:**
- Consumes: `counting_review` from Task 2, `Post.graded_at` from Task 1.
- Produces: `examenes_rubro(db, user_id, klass, now)` — same signature, new gating.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_grades_engine.py`:

```python
from app.services.grades import examenes_rubro


def _examen(db, teacher, klass, mode="paper", graded_at=None):
    p = Post(author_id=teacher.id, class_id=klass.id, type="examen",
             content="parcial", examen_mode=mode, graded_at=graded_at)
    db.add(p)
    db.commit()
    return p


def test_ungraded_examen_does_not_count(db, student, teacher, klass, enrolled):
    _examen(db, teacher, klass)                       # graded_at is None
    r = examenes_rubro(db, student.id, klass, now=DUE)
    assert r.evaluated is False
    assert r.points == Decimal("0")


def test_graded_paper_examen_scores_from_the_review(db, student, teacher, klass, enrolled):
    x = _examen(db, teacher, klass, graded_at=DUE)
    _review(db, teacher, x, student, None, "8")       # 1–10 scale
    r = examenes_rubro(db, student.id, klass, now=DUE)
    assert r.evaluated is True
    assert r.points == Decimal("8") / Decimal("10") * klass.examenes_weight


def test_graded_examen_with_no_review_scores_zero(db, student, teacher, klass, enrolled):
    _examen(db, teacher, klass, graded_at=DUE)
    r = examenes_rubro(db, student.id, klass, now=DUE)
    assert r.evaluated is True
    assert r.points == Decimal("0")
    assert r.count_due == 1


def test_digital_examen_scores_the_same_as_paper(db, student, teacher, klass, enrolled):
    x = _examen(db, teacher, klass, mode="digital", graded_at=DUE)
    e = _entrega(db, student, x, DUE - timedelta(hours=1))
    _review(db, teacher, x, student, e, "8")
    r = examenes_rubro(db, student.id, klass, now=DUE)
    assert r.points == Decimal("8") / Decimal("10") * klass.examenes_weight


def test_unmarking_graded_removes_the_examen_again(db, student, teacher, klass, enrolled):
    x = _examen(db, teacher, klass, graded_at=DUE)
    _review(db, teacher, x, student, None, "8")
    x.graded_at = None
    db.commit()
    r = examenes_rubro(db, student.id, klass, now=DUE)
    assert r.evaluated is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_grades_engine.py -k examen -v`
Expected: FAIL — `_examen()` passes `examen_mode`/`graded_at`, and the rubro still filters on `due_date`.

- [ ] **Step 3: Implement**

Replace the body of `examenes_rubro` in `backend/app/services/grades.py`:

```python
def examenes_rubro(db: Session, user_id: int, klass: Class, now: datetime) -> Rubro:
    """An examen counts only once the teacher marks it calificado.

    Unlike a tarea, an examen has no auto-score: until somebody types a number
    there is nothing to average, so an ungraded examen stays invisible instead
    of reading as a zero. Once graded, it counts for every active enrollment —
    a student with no review scored 0, which is the 'didn't take it' case.
    """
    graded = (
        db.query(Post)
        .filter(Post.class_id == klass.id,
                Post.type == "examen",
                Post.status == "active",
                Post.graded_at.isnot(None))
        .all()
    )
    weight = klass.examenes_weight
    if not graded:
        return Rubro(evaluated=False, points=Decimal("0"), weight=weight)

    total = Decimal("0")
    entregadas = 0
    for examen in graded:
        entrega = _counting_entrega(db, user_id, examen.id)
        if entrega is not None:
            entregadas += 1
        review = counting_review(db, examen.id, user_id, entrega)
        if review is not None and review.score is not None:
            total += Decimal(review.score) / Decimal("10")   # 1–10 scale
    points = (total / len(graded)) * weight
    return Rubro(evaluated=True, points=points, weight=weight,
                 count_due=len(graded), count_entregadas=entregadas)
```

- [ ] **Step 4: Run the full suite**

Run: `cd backend && ../venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/grades.py backend/tests/test_grades_engine.py
git commit -m "feat(backend): examenes count only when marked calificado"
```

---

### Task 4: Engine — empty rubro pays full weight at end of course

**Files:**
- Modify: `backend/app/services/grades.py`
- Test: `backend/tests/test_grades_engine.py`

**Interfaces:**
- Consumes: `Rubro` dataclass.
- Produces: `empty_rubro_payout(klass, weight: int, now: datetime, has_items: bool) -> Optional[Rubro]` — returns a full-weight `Rubro` when the course is over and the rubro never had items, else `None`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_grades_engine.py`:

```python
from datetime import date

AFTER_COURSE = datetime(2027, 1, 15, tzinfo=timezone.utc)   # klass.end_date is 2026-12-04


def test_rubro_with_no_items_pays_full_weight_after_the_course_ends(db, student, teacher, klass, enrolled):
    r = examenes_rubro(db, student.id, klass, now=AFTER_COURSE)
    assert r.evaluated is True
    assert r.points == Decimal(klass.examenes_weight)


def test_rubro_with_no_items_pays_nothing_before_the_course_ends(db, student, teacher, klass, enrolled):
    r = examenes_rubro(db, student.id, klass, now=DUE)
    assert r.evaluated is False
    assert r.points == Decimal("0")


def test_an_ungraded_examen_still_counts_as_having_items(db, student, teacher, klass, enrolled):
    _examen(db, teacher, klass)                      # exists, never graded
    r = examenes_rubro(db, student.id, klass, now=AFTER_COURSE)
    assert r.evaluated is False                      # NOT a free 30
    assert r.points == Decimal("0")


def test_tareas_rubro_also_pays_out_when_none_were_ever_assigned(db, student, teacher, klass, enrolled):
    r = tareas_rubro(db, student.id, klass, now=AFTER_COURSE)
    assert r.evaluated is True
    assert r.points == Decimal(klass.tareas_weight)


def test_a_student_who_skipped_every_tarea_still_scores_zero(db, student, teacher, klass, enrolled):
    _tarea(db, teacher, klass, DUE)
    r = tareas_rubro(db, student.id, klass, now=AFTER_COURSE)
    assert r.evaluated is True
    assert r.points == Decimal("0")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_grades_engine.py -k pays -v`
Expected: FAIL — an empty rubro currently returns `evaluated=False` regardless of the date.

- [ ] **Step 3: Implement**

Add to `backend/app/services/grades.py` above `tareas_rubro`:

```python
def empty_rubro_payout(klass: Class, weight: int, now: datetime,
                       has_items: bool) -> Optional[Rubro]:
    """Full weight for a rubro that never had a single item, once the course ends.

    Nobody is penalised for work the teacher chose not to assign, and the
    reachable maximum stays where students believed it was all semester. An item
    that exists but was never graded still counts as an item — this rule is for
    the teacher who assigned no exámenes at all, not the one who has not
    finished grading.
    """
    if has_items or klass.end_date is None or now.date() <= klass.end_date:
        return None
    return Rubro(evaluated=True, points=Decimal(weight), weight=weight,
                 count_due=0, count_entregadas=0)
```

In `tareas_rubro`, replace the `if not due_tareas:` block:

```python
    all_tareas = (
        db.query(Post)
        .filter(Post.class_id == klass.id, Post.type == "tarea",
                Post.status == "active")
        .count()
    )
    payout = empty_rubro_payout(klass, weight, now, has_items=all_tareas > 0)
    if payout is not None:
        return payout
    if not due_tareas:
        return Rubro(evaluated=False, points=Decimal("0"), weight=weight)
```

Note the ordering: `weight = klass.tareas_weight` must be assigned before this block — move that line above it if needed.

In `examenes_rubro`, replace the `if not graded:` block:

```python
    all_examenes = (
        db.query(Post)
        .filter(Post.class_id == klass.id, Post.type == "examen",
                Post.status == "active")
        .count()
    )
    payout = empty_rubro_payout(klass, weight, now, has_items=all_examenes > 0)
    if payout is not None:
        return payout
    if not graded:
        return Rubro(evaluated=False, points=Decimal("0"), weight=weight)
```

- [ ] **Step 4: Run the full suite**

Run: `cd backend && ../venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/grades.py backend/tests/test_grades_engine.py
git commit -m "feat(backend): empty rubro pays full weight after the course ends"
```

---

### Task 5: `examen` post type and the calificado flip

**Files:**
- Modify: `backend/app/routers/posts.py`, `backend/app/schemas.py`
- Test: `backend/tests/test_examenes.py` (create)

**Interfaces:**
- Consumes: `Post.examen_mode`, `Post.graded_at`.
- Produces: `POST /api/posts` accepting `type=examen` + `examen_mode`; `POST /api/posts/{id}/graded` and `DELETE /api/posts/{id}/graded` returning `{"graded_at": <iso|null>}`. `PostOut` gains `examen_mode: Optional[str]` and `graded_at: Optional[datetime]`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_examenes.py`:

```python
def _make_examen(client, headers, klass, mode="paper"):
    return client.post("/api/posts", data={
        "content": "Parcial 1", "type": "examen",
        "class_id": str(klass.id), "examen_mode": mode,
    }, headers=headers)


def test_teacher_creates_a_paper_examen(client, teacher_headers, klass):
    r = _make_examen(client, teacher_headers, klass)
    assert r.status_code == 201, r.text
    assert r.json()["examen_mode"] == "paper"
    assert r.json()["graded_at"] is None


def test_examen_mode_defaults_to_paper(client, teacher_headers, klass):
    r = client.post("/api/posts", data={
        "content": "Parcial", "type": "examen", "class_id": str(klass.id),
    }, headers=teacher_headers)
    assert r.json()["examen_mode"] == "paper"


def test_invalid_examen_mode_is_rejected(client, teacher_headers, klass):
    r = _make_examen(client, teacher_headers, klass, mode="oral")
    assert r.status_code == 422


def test_student_cannot_create_an_examen(client, auth_headers, klass):
    r = _make_examen(client, auth_headers, klass)
    assert r.status_code == 403


def test_teacher_marks_and_unmarks_calificado(client, teacher_headers, klass):
    examen_id = _make_examen(client, teacher_headers, klass).json()["id"]
    r = client.post(f"/api/posts/{examen_id}/graded", headers=teacher_headers)
    assert r.status_code == 200
    assert r.json()["graded_at"] is not None
    r = client.delete(f"/api/posts/{examen_id}/graded", headers=teacher_headers)
    assert r.json()["graded_at"] is None


def test_only_a_tarea_or_examen_can_be_marked_graded(client, db, teacher_headers, auth_headers, klass, enrolled):
    post_id = client.post("/api/posts", data={"content": "hola"},
                          headers=auth_headers).json()["id"]
    r = client.post(f"/api/posts/{post_id}/graded", headers=teacher_headers)
    assert r.status_code == 422


def test_student_cannot_mark_calificado(client, teacher_headers, auth_headers, klass):
    examen_id = _make_examen(client, teacher_headers, klass).json()["id"]
    r = client.post(f"/api/posts/{examen_id}/graded", headers=auth_headers)
    assert r.status_code == 403
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_examenes.py -v`
Expected: FAIL — 422 "Tipo de publicación inválido".

- [ ] **Step 3: Accept the examen type in the composer endpoint**

In `backend/app/routers/posts.py`, add the form field to `create_post`:

```python
    examen_mode: Optional[str] = Form(None),
```

Extend the type guard:

```python
    if type not in ("regular", "participacion", "tarea", "examen"):
        raise HTTPException(status_code=422, detail="Tipo de publicación inválido")
```

Replace the tarea-only teacher guard:

```python
    if type in ("tarea", "examen") and user.role != "teacher":
        raise HTTPException(status_code=403,
                            detail="Solo el profesor puede crear tareas y exámenes")
    if type == "examen":
        examen_mode = examen_mode or "paper"
        if examen_mode not in ("paper", "digital"):
            raise HTTPException(status_code=422, detail="Modalidad de examen inválida")
```

Extend the class requirement (it currently names tareas only):

```python
    if type in ("tarea", "examen") and resolved_class is None:
        raise HTTPException(status_code=422, detail="Una tarea necesita una clase")
```

And in the `Post(...)` constructor add:

```python
        examen_mode=examen_mode if type == "examen" else None,
```

- [ ] **Step 4: Add the graded endpoints**

Append to `backend/app/routers/posts.py`:

```python
def _teacher_item(db: Session, post_id: int, user: User) -> Post:
    """A tarea/examen in a class this teacher owns, or the right HTTP error."""
    post = db.get(Post, post_id)
    if post is None or post.status != "active":
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Solo el profesor puede calificar")
    if post.type not in ("tarea", "examen"):
        raise HTTPException(status_code=422, detail="Esta publicación no se califica")
    klass = db.get(Class, post.class_id) if post.class_id else None
    if klass is None or klass.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="No eres profesor de esa clase")
    return post


@router.post("/{post_id}/graded")
def mark_graded(post_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    post = _teacher_item(db, post_id, user)
    post.graded_at = utcnow()
    db.commit()
    return {"graded_at": post.graded_at}


@router.delete("/{post_id}/graded")
def unmark_graded(post_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    post = _teacher_item(db, post_id, user)
    post.graded_at = None
    db.commit()
    return {"graded_at": None}
```

- [ ] **Step 5: Expose the fields**

In `backend/app/schemas.py`, add to `PostOut` after `is_entrega`:

```python
    examen_mode: Optional[str] = None
    graded_at: Optional[datetime] = None
```

In `serialize_post` in `posts.py`, add:

```python
        examen_mode=post.examen_mode,
        graded_at=post.graded_at,
```

- [ ] **Step 6: Run the full suite**

Run: `cd backend && ../venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/posts.py backend/app/schemas.py backend/tests/test_examenes.py
git commit -m "feat(backend): examen post type with paper/digital modes and the calificado flip"
```

---

### Task 6: `PUT /api/reviews` — the single write path

**Files:**
- Create: `backend/app/routers/reviews.py`
- Modify: `backend/app/main.py` (register the router), `backend/app/schemas.py`
- Test: `backend/tests/test_reviews_api.py` (create)

**Interfaces:**
- Consumes: `_teacher_item` from Task 5, `Review` from Task 1.
- Produces: `PUT /api/reviews` accepting JSON `{item_post_id, student_id, entrega_post_id?, score?, feedback?}` → `ReviewOut {id, item_post_id, student_id, entrega_post_id, score, auto_score, feedback, updated_at}`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_reviews_api.py`:

```python
from datetime import datetime, timedelta, timezone

from app.models import Post

DUE = datetime(2026, 8, 9, 23, 59, tzinfo=timezone.utc)


def _tarea(db, teacher, klass):
    p = Post(author_id=teacher.id, class_id=klass.id, type="tarea",
             content="t", due_date=DUE)
    db.add(p)
    db.commit()
    return p


def _entrega(db, student, tarea, at=DUE - timedelta(hours=1)):
    p = Post(author_id=student.id, class_id=tarea.class_id, type="regular",
             parent_id=tarea.id, content="e", is_entrega=True, created_at=at)
    db.add(p)
    db.commit()
    return p


def _body(tarea, student, entrega=None, score=90, feedback=None):
    return {"item_post_id": tarea.id, "student_id": student.id,
            "entrega_post_id": entrega.id if entrega else None,
            "score": score, "feedback": feedback}


def test_teacher_scores_an_entrega(client, db, teacher_headers, teacher, student, klass, enrolled):
    t = _tarea(db, teacher, klass)
    e = _entrega(db, student, t)
    r = client.put("/api/reviews", json=_body(t, student, e, 85, "bien"),
                   headers=teacher_headers)
    assert r.status_code == 200, r.text
    assert float(r.json()["score"]) == 85.0
    assert r.json()["feedback"] == "bien"


def test_second_write_updates_instead_of_duplicating(client, db, teacher_headers, teacher, student, klass, enrolled):
    from app.models import Review

    t = _tarea(db, teacher, klass)
    e = _entrega(db, student, t)
    first = client.put("/api/reviews", json=_body(t, student, e, 85), headers=teacher_headers)
    second = client.put("/api/reviews", json=_body(t, student, e, 95), headers=teacher_headers)
    assert first.json()["id"] == second.json()["id"]
    assert float(second.json()["score"]) == 95.0
    assert db.query(Review).count() == 1


def test_tarea_score_above_100_is_rejected(client, db, teacher_headers, teacher, student, klass, enrolled):
    t = _tarea(db, teacher, klass)
    e = _entrega(db, student, t)
    r = client.put("/api/reviews", json=_body(t, student, e, 120), headers=teacher_headers)
    assert r.status_code == 422
    assert "0" in r.json()["detail"] and "100" in r.json()["detail"]


def test_examen_score_above_10_is_rejected(client, db, teacher_headers, teacher, student, klass, enrolled):
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen",
             content="p", examen_mode="paper")
    db.add(x)
    db.commit()
    r = client.put("/api/reviews",
                   json={"item_post_id": x.id, "student_id": student.id, "score": 85},
                   headers=teacher_headers)
    assert r.status_code == 422


def test_paper_examen_review_needs_no_entrega(client, db, teacher_headers, teacher, student, klass, enrolled):
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen",
             content="p", examen_mode="paper")
    db.add(x)
    db.commit()
    r = client.put("/api/reviews",
                   json={"item_post_id": x.id, "student_id": student.id, "score": 9},
                   headers=teacher_headers)
    assert r.status_code == 200
    assert r.json()["entrega_post_id"] is None


def test_student_cannot_write_a_review(client, db, auth_headers, teacher, student, klass, enrolled):
    t = _tarea(db, teacher, klass)
    e = _entrega(db, student, t)
    r = client.put("/api/reviews", json=_body(t, student, e), headers=auth_headers)
    assert r.status_code == 403


def test_reviewing_a_student_not_enrolled_is_rejected(client, db, teacher_headers, teacher, student, klass):
    # no `enrolled` fixture: the student is not in the class
    t = _tarea(db, teacher, klass)
    r = client.put("/api/reviews", json=_body(t, student, None), headers=teacher_headers)
    assert r.status_code == 422
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_reviews_api.py -v`
Expected: FAIL — 404/405, the route does not exist.

- [ ] **Step 3: Add the schemas**

In `backend/app/schemas.py`:

```python
class ReviewIn(BaseModel):
    item_post_id: int
    student_id: int
    entrega_post_id: Optional[int] = None
    score: Optional[Decimal] = None
    feedback: Optional[str] = None


class ReviewOut(BaseModel):
    id: int
    item_post_id: int
    student_id: int
    entrega_post_id: Optional[int]
    score: Optional[Decimal]
    auto_score: Optional[Decimal]
    feedback: Optional[str]
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
```

Add `from decimal import Decimal` if the module does not already import it, and reuse the existing `ConfigDict` import style used by the other Out schemas in this file.

- [ ] **Step 4: Implement the router**

Create `backend/app/routers/reviews.py`:

```python
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Class, Enrollment, Post, Review, User, utcnow
from app.routers.posts import _teacher_item
from app.schemas import ReviewIn, ReviewOut
from app.services.grades import lateness_score

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

SCALES = {"tarea": (Decimal("0"), Decimal("100")),
          "examen": (Decimal("1"), Decimal("10"))}


def _check_scale(item_type: str, score: Optional[Decimal]) -> None:
    if score is None:
        return
    low, high = SCALES[item_type]
    if not (low <= score <= high):
        raise HTTPException(
            status_code=422,
            detail=f"La calificación debe estar entre {low} y {high}")


@router.put("", response_model=ReviewOut)
def upsert_review(body: ReviewIn, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    item = _teacher_item(db, body.item_post_id, user)
    _check_scale(item.type, body.score)

    enrolled = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == body.student_id,
                Enrollment.class_id == item.class_id,
                Enrollment.status == "active")
        .first()
    )
    if enrolled is None:
        raise HTTPException(status_code=422,
                            detail="Ese alumno no está inscrito en la clase")

    auto = None
    if body.entrega_post_id is not None and item.due_date is not None:
        entrega = db.get(Post, body.entrega_post_id)
        if entrega is None or entrega.parent_id != item.id:
            raise HTTPException(status_code=422,
                                detail="Esa entrega no pertenece a esta tarea")
        auto = lateness_score(entrega.created_at, item.due_date)

    review = (
        db.query(Review)
        .filter(Review.item_post_id == item.id,
                Review.student_id == body.student_id)
        .first()
    )
    if review is None:
        review = Review(item_post_id=item.id, student_id=body.student_id)
        db.add(review)
    review.entrega_post_id = body.entrega_post_id
    review.score = body.score
    review.auto_score = auto
    review.feedback = body.feedback
    review.reviewer_id = user.id
    review.updated_at = utcnow()
    db.commit()
    db.refresh(review)
    return review
```

Register it in `backend/app/main.py` next to the other routers:

```python
from app.routers import reviews
app.include_router(reviews.router)
```

- [ ] **Step 5: Run the full suite**

Run: `cd backend && ../venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/reviews.py backend/app/schemas.py backend/app/main.py backend/tests/test_reviews_api.py
git commit -m "feat(backend): PUT /api/reviews upsert with per-type scale validation"
```

---

### Task 7: Veto and un-veto — and the delete-vs-veto ledger fix

**Files:**
- Modify: `backend/app/services/points.py`, `backend/app/routers/posts.py`
- Test: `backend/tests/test_veto.py` (create), `backend/tests/test_points_service.py`

**Interfaces:**
- Consumes: `points.revoke_for_source`.
- Produces: `points.restore_for_source(db, *, source_type, source_id) -> int`; `points.veto_post(db, *, post, revoked_by) -> int`; `points.unveto_post(db, *, post) -> int`; `POST /api/posts/{id}/veto` and `DELETE /api/posts/{id}/veto`.

**Context — a real bug this task fixes.** `remove_post` currently calls `revoke_post` on *both* branches: the author deleting their own post and the teacher vetoing it. CLAUDE.md's rule is `deleted ≠ vetoed` — deletion keeps earned points, only a veto revokes. Deletion must stop revoking. Separately, per spec §2.8 a veto must not touch the post's likes.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_veto.py`:

```python
from decimal import Decimal

from app.models import PointsLedger, Post


def _participacion(client, headers):
    return client.post("/api/posts", data={
        "content": "Expliqué el modelo de oferta y demanda", "type": "participacion",
        "taps": "3",
    }, headers=headers)


def _active_points(db, user_id) -> Decimal:
    rows = db.query(PointsLedger).filter(PointsLedger.user_id == user_id,
                                         PointsLedger.revoked_at.is_(None)).all()
    return sum((r.points for r in rows), Decimal("0"))


def test_veto_revokes_the_participacion_points(client, db, teacher_headers, auth_headers, student, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    assert _active_points(db, student.id) == Decimal("3.0")
    r = client.post(f"/api/posts/{pid}/veto", json={"reason": "no fue en clase"},
                    headers=teacher_headers)
    assert r.status_code == 200
    db.expire_all()
    assert _active_points(db, student.id) == Decimal("0")
    assert db.get(Post, pid).status == "vetoed"
    assert db.get(Post, pid).veto_reason == "no fue en clase"


def test_unveto_restores_them(client, db, teacher_headers, auth_headers, student, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    client.post(f"/api/posts/{pid}/veto", headers=teacher_headers)
    r = client.delete(f"/api/posts/{pid}/veto", headers=teacher_headers)
    assert r.status_code == 200
    db.expire_all()
    assert _active_points(db, student.id) == Decimal("3.0")
    assert db.get(Post, pid).status == "active"
    assert db.get(Post, pid).veto_reason is None


def test_veto_leaves_likes_alone(client, db, teacher_headers, auth_headers, student2_headers, student, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    client.post(f"/api/posts/{pid}/like", headers=student2_headers)
    assert _active_points(db, student.id) == Decimal("4.0")     # 3 taps + 1 like
    client.post(f"/api/posts/{pid}/veto", headers=teacher_headers)
    db.expire_all()
    assert _active_points(db, student.id) == Decimal("1.0")     # the like survives


def test_deleting_your_own_post_keeps_the_points(client, db, auth_headers, student, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    client.delete(f"/api/posts/{pid}", headers=auth_headers)
    db.expire_all()
    assert db.get(Post, pid).status == "deleted"
    assert _active_points(db, student.id) == Decimal("3.0")     # deleted != vetoed


def test_student_cannot_veto(client, auth_headers, student2_headers, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    r = client.post(f"/api/posts/{pid}/veto", headers=student2_headers)
    assert r.status_code == 403
```

In `backend/tests/test_points_service.py`, rename `test_revoke_post_revokes_everything` to `test_veto_post_revokes_taps_but_not_likes` and change its assertion to expect only the participación row revoked.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_veto.py -v`
Expected: FAIL — 404 on `/veto`, and `test_deleting_your_own_post_keeps_the_points` fails because deletion currently revokes.

- [ ] **Step 3: Rework the points service**

In `backend/app/services/points.py`, replace `revoke_post` with:

```python
def restore_for_source(db: Session, *, source_type: str, source_id: int) -> int:
    """Undo a revocation. The row is never deleted, only un-flagged."""
    rows = (
        db.query(PointsLedger)
        .filter(
            PointsLedger.source_type == source_type,
            PointsLedger.source_id == source_id,
            PointsLedger.revoked_at.isnot(None),
        )
        .all()
    )
    for row in rows:
        row.revoked_at = None
        row.revoked_by = None
    db.flush()
    return len(rows)


def veto_post(db: Session, *, post: Post, revoked_by: int) -> int:
    """Revoke what the post itself earned. Likes it received are NOT touched —
    a like is the liker's action, not the author's claim."""
    return revoke_for_source(db, source_type="participacion", source_id=post.id,
                             revoked_by=revoked_by)


def unveto_post(db: Session, *, post: Post) -> int:
    return restore_for_source(db, source_type="participacion", source_id=post.id)
```

- [ ] **Step 4: Fix deletion and add the veto endpoints**

In `backend/app/routers/posts.py`, `remove_post`: delete the `points.revoke_post(...)` line entirely and replace the branch bodies:

```python
    if post.author_id == user.id:
        post.status = "deleted"          # deleted != vetoed: points are kept
    elif user.role == "teacher":
        post.status = "vetoed"
        points.veto_post(db, post=post, revoked_by=user.id)
    else:
        raise HTTPException(status_code=403, detail="No puedes eliminar esta publicación")
```

Append the endpoints:

```python
class VetoIn(BaseModel):
    reason: Optional[str] = None


def _teacher_of_post(db: Session, post_id: int, user: User) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Solo el profesor puede vetar")
    klass = db.get(Class, post.class_id) if post.class_id else None
    if klass is None or klass.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="No eres profesor de esa clase")
    return post


@router.post("/{post_id}/veto")
def veto(post_id: int, body: VetoIn = VetoIn(),
         user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = _teacher_of_post(db, post_id, user)
    post.status = "vetoed"
    post.veto_reason = body.reason
    points.veto_post(db, post=post, revoked_by=user.id)
    db.commit()
    return {"status": post.status, "veto_reason": post.veto_reason}


@router.delete("/{post_id}/veto")
def unveto(post_id: int, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    post = _teacher_of_post(db, post_id, user)
    post.status = "active"
    post.veto_reason = None
    points.unveto_post(db, post=post)
    db.commit()
    return {"status": post.status, "veto_reason": None}
```

Add `from pydantic import BaseModel` to the imports at the top of `posts.py`.

- [ ] **Step 5: Run the full suite**

Run: `cd backend && ../venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/points.py backend/app/routers/posts.py backend/tests/test_veto.py backend/tests/test_points_service.py
git commit -m "fix(backend): deletion keeps points, veto revokes them and spares likes"
```

---

### Task 8: The Revisar read endpoints

**Files:**
- Create: `backend/app/routers/review_queue.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_review_queue.py` (create)

**Interfaces:**
- Consumes: `Review`, `Post`, `Enrollment`, `counting_review`, `_counting_entrega`, `lateness_score`.
- Produces:
  - `GET /api/review/entregas?class_id=&status=unopened|all` → `{"groups": [{"tarea": {"id", "content", "due_date"}, "pending": int, "entregas": [{"student": {"id","username","name"}, "entrega_post_id", "created_at", "auto_score", "reviewed": bool, "score"}]}]}`
  - `GET /api/review/examenes?class_id=` → `{"items": [{"id", "content", "examen_mode", "graded_at", "created_at"}]}`
  - `GET /api/review/examenes/{id}` → `{"examen": {"id","content","examen_mode","graded_at"}, "rows": [{"student": {...}, "entrega_post_id", "score"}]}`
  - `GET /api/review/participaciones?class_id=&limit=` → `{"items": [{"post_id","student","content","taps","points","vetoed","veto_reason","created_at"}]}`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_review_queue.py`:

```python
from datetime import datetime, timedelta, timezone

from app.models import Post

DUE = datetime(2026, 8, 9, 23, 59, tzinfo=timezone.utc)


def _tarea(db, teacher, klass):
    p = Post(author_id=teacher.id, class_id=klass.id, type="tarea", content="Cap 3",
             due_date=DUE)
    db.add(p)
    db.commit()
    return p


def _entrega(db, student, tarea, at=DUE - timedelta(hours=2)):
    p = Post(author_id=student.id, class_id=tarea.class_id, type="regular",
             parent_id=tarea.id, content="mi entrega", is_entrega=True, created_at=at)
    db.add(p)
    db.commit()
    return p


def test_entregas_queue_groups_by_tarea(client, db, teacher_headers, teacher, student, klass, enrolled):
    t = _tarea(db, teacher, klass)
    _entrega(db, student, t)
    r = client.get(f"/api/review/entregas?class_id={klass.id}", headers=teacher_headers)
    assert r.status_code == 200, r.text
    groups = r.json()["groups"]
    assert len(groups) == 1
    assert groups[0]["tarea"]["id"] == t.id
    assert groups[0]["pending"] == 1
    assert float(groups[0]["entregas"][0]["auto_score"]) == 100.0
    assert groups[0]["entregas"][0]["reviewed"] is False


def test_reviewed_entregas_drop_out_of_the_unopened_filter(client, db, teacher_headers, teacher, student, klass, enrolled):
    t = _tarea(db, teacher, klass)
    e = _entrega(db, student, t)
    client.put("/api/reviews", json={"item_post_id": t.id, "student_id": student.id,
                                     "entrega_post_id": e.id, "score": 100},
               headers=teacher_headers)
    r = client.get(f"/api/review/entregas?class_id={klass.id}&status=unopened",
                   headers=teacher_headers)
    assert r.json()["groups"] == []
    r = client.get(f"/api/review/entregas?class_id={klass.id}&status=all",
                   headers=teacher_headers)
    assert r.json()["groups"][0]["entregas"][0]["reviewed"] is True


def test_examenes_list_returns_the_classes_examenes(client, db, teacher_headers, teacher, klass):
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen", content="P1",
             examen_mode="paper")
    db.add(x)
    db.commit()
    r = client.get(f"/api/review/examenes?class_id={klass.id}", headers=teacher_headers)
    assert r.status_code == 200
    assert [i["id"] for i in r.json()["items"]] == [x.id]
    assert r.json()["items"][0]["examen_mode"] == "paper"


def test_examen_roster_lists_every_active_enrollment(client, db, teacher_headers, teacher, student, student2, klass, enrolled):
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen", content="P1",
             examen_mode="paper")
    db.add(x)
    db.commit()
    r = client.get(f"/api/review/examenes/{x.id}", headers=teacher_headers)
    assert r.status_code == 200
    ids = {row["student"]["id"] for row in r.json()["rows"]}
    assert {student.id, student2.id} <= ids
    assert r.json()["examen"]["graded_at"] is None


def test_participaciones_list_shows_veto_state(client, db, teacher_headers, auth_headers, klass, enrolled):
    pid = client.post("/api/posts", data={"content": "Participé explicando el modelo",
                                          "type": "participacion", "taps": "2"},
                      headers=auth_headers).json()["id"]
    client.post(f"/api/posts/{pid}/veto", json={"reason": "no aplica"}, headers=teacher_headers)
    r = client.get(f"/api/review/participaciones?class_id={klass.id}", headers=teacher_headers)
    row = next(i for i in r.json()["items"] if i["post_id"] == pid)
    assert row["vetoed"] is True
    assert row["veto_reason"] == "no aplica"
    assert row["taps"] == 2


def test_another_teacher_cannot_read_the_queue(client, db, klass, teacher):
    from app.auth.sessions import create_session
    from app.models import User

    other = User(google_id="g-other", email="otro@example.com", name="Otro", role="teacher")
    db.add(other)
    db.commit()
    headers = {"Authorization": f"Bearer {create_session(db, other)}"}
    r = client.get(f"/api/review/entregas?class_id={klass.id}", headers=headers)
    assert r.status_code == 403


def test_student_cannot_read_the_queue(client, auth_headers, klass, enrolled):
    r = client.get(f"/api/review/entregas?class_id={klass.id}", headers=auth_headers)
    assert r.status_code == 403
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_review_queue.py -v`
Expected: FAIL — 404, the router does not exist.

- [ ] **Step 3: Implement the router**

Create `backend/app/routers/review_queue.py`:

```python
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Class, Enrollment, Post, PointsLedger, Review, User
from app.services.grades import _counting_entrega, counting_review, lateness_score

router = APIRouter(prefix="/api/review", tags=["review"])


def _owned_class(db: Session, class_id: int, user: User) -> Class:
    klass = db.get(Class, class_id)
    if klass is None:
        raise HTTPException(status_code=404, detail="Clase no encontrada")
    if user.role != "teacher" or klass.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="No eres profesor de esa clase")
    return klass


def _student_json(u: User) -> dict:
    return {"id": u.id, "username": u.username, "name": u.name}


def _active_students(db: Session, class_id: int) -> list[User]:
    rows = (
        db.query(User)
        .join(Enrollment, Enrollment.user_id == User.id)
        .filter(Enrollment.class_id == class_id, Enrollment.status == "active")
        .all()
    )
    return sorted(rows, key=lambda u: (u.username or "", u.id))


@router.get("/entregas")
def entregas_queue(class_id: int, status: str = Query("unopened"),
                   user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    klass = _owned_class(db, class_id, user)
    tareas = (
        db.query(Post)
        .filter(Post.class_id == klass.id, Post.type == "tarea", Post.status == "active")
        .order_by(Post.due_date.desc())
        .all()
    )
    groups = []
    for tarea in tareas:
        entregas = []
        for student in _active_students(db, klass.id):
            entrega = _counting_entrega(db, student.id, tarea.id)
            if entrega is None:
                continue
            review = counting_review(db, tarea.id, student.id, entrega)
            reviewed = review is not None
            if status == "unopened" and reviewed:
                continue
            auto = (lateness_score(entrega.created_at, tarea.due_date)
                    if tarea.due_date is not None else None)
            entregas.append({
                "student": _student_json(student),
                "entrega_post_id": entrega.id,
                "created_at": entrega.created_at,
                "auto_score": float(auto) if auto is not None else None,
                "reviewed": reviewed,
                "score": float(review.score) if reviewed and review.score is not None else None,
            })
        if not entregas:
            continue
        groups.append({
            "tarea": {"id": tarea.id, "content": tarea.content, "due_date": tarea.due_date},
            "pending": sum(1 for e in entregas if not e["reviewed"]),
            "entregas": entregas,
        })
    return {"groups": groups}


@router.get("/examenes")
def examenes_list(class_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    klass = _owned_class(db, class_id, user)
    rows = (
        db.query(Post)
        .filter(Post.class_id == klass.id, Post.type == "examen",
                Post.status == "active")
        .order_by(Post.created_at.desc())
        .all()
    )
    return {"items": [{"id": p.id, "content": p.content,
                       "examen_mode": p.examen_mode, "graded_at": p.graded_at,
                       "created_at": p.created_at} for p in rows]}


@router.get("/examenes/{examen_id}")
def examen_roster(examen_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    examen = db.get(Post, examen_id)
    if examen is None or examen.type != "examen":
        raise HTTPException(status_code=404, detail="Examen no encontrado")
    _owned_class(db, examen.class_id, user)
    rows = []
    for student in _active_students(db, examen.class_id):
        entrega = _counting_entrega(db, student.id, examen.id)
        review = (
            db.query(Review)
            .filter(Review.item_post_id == examen.id, Review.student_id == student.id)
            .first()
        )
        rows.append({
            "student": _student_json(student),
            "entrega_post_id": entrega.id if entrega else None,
            "score": float(review.score) if review and review.score is not None else None,
        })
    return {"examen": {"id": examen.id, "content": examen.content,
                       "examen_mode": examen.examen_mode, "graded_at": examen.graded_at},
            "rows": rows}


@router.get("/participaciones")
def participaciones(class_id: int, limit: int = Query(50, ge=1, le=200),
                    user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    klass = _owned_class(db, class_id, user)
    posts = (
        db.query(Post)
        .filter(Post.class_id == klass.id, Post.type == "participacion")
        .order_by(Post.created_at.desc())
        .limit(limit)
        .all()
    )
    items = []
    for p in posts:
        row = (
            db.query(PointsLedger)
            .filter(PointsLedger.source_type == "participacion",
                    PointsLedger.source_id == p.id)
            .first()
        )
        items.append({
            "post_id": p.id,
            "student": _student_json(p.author),
            "content": p.content,
            "taps": p.taps,
            "points": float(row.points) if row is not None else 0.0,
            "vetoed": p.status == "vetoed",
            "veto_reason": p.veto_reason,
            "created_at": p.created_at,
        })
    return {"items": items}
```

Register it in `backend/app/main.py`:

```python
from app.routers import review_queue
app.include_router(review_queue.router)
```

- [ ] **Step 4: Run the full suite**

Run: `cd backend && ../venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/review_queue.py backend/app/main.py backend/tests/test_review_queue.py
git commit -m "feat(backend): Revisar read endpoints for entregas, examenes and participaciones"
```

---

### Task 9: Scores are private to their author

**Files:**
- Modify: `backend/app/routers/posts.py` (`serialize_post`, `get_thread`, `get_feed`), `backend/app/schemas.py`
- Test: `backend/tests/test_review_privacy.py` (create)

**Interfaces:**
- Consumes: `Review` from Task 1.
- Produces: `PostOut.my_review: Optional[ReviewOut]` and `PostOut.veto_reason: Optional[str]`, populated only when the requester is the post's author or the class's teacher. `serialize_post(post, liked_ids, viewer=None, review_by_post=None)` — the two new parameters are keyword-only with defaults, so existing call sites keep working.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_review_privacy.py`:

```python
from datetime import datetime, timedelta, timezone

from app.models import Post

DUE = datetime(2026, 8, 9, 23, 59, tzinfo=timezone.utc)


def _graded_entrega(client, db, teacher, teacher_headers, student, klass):
    t = Post(author_id=teacher.id, class_id=klass.id, type="tarea", content="Cap 3",
             due_date=DUE)
    db.add(t)
    db.commit()
    e = Post(author_id=student.id, class_id=klass.id, type="regular", parent_id=t.id,
             content="mi entrega", is_entrega=True, created_at=DUE - timedelta(hours=1))
    db.add(e)
    db.commit()
    client.put("/api/reviews",
               json={"item_post_id": t.id, "student_id": student.id,
                     "entrega_post_id": e.id, "score": 88, "feedback": "muy bien"},
               headers=teacher_headers)
    return t, e


def _reply(thread_json, post_id):
    return next(r for r in thread_json["replies"] if r["id"] == post_id)


def test_the_author_sees_their_own_score(client, db, teacher, teacher_headers, auth_headers, student, klass, enrolled):
    t, e = _graded_entrega(client, db, teacher, teacher_headers, student, klass)
    r = client.get(f"/api/posts/{t.id}", headers=auth_headers)
    review = _reply(r.json(), e.id)["my_review"]
    assert float(review["score"]) == 88.0
    assert review["feedback"] == "muy bien"


def test_the_teacher_sees_it_too(client, db, teacher, teacher_headers, student, klass, enrolled):
    t, e = _graded_entrega(client, db, teacher, teacher_headers, student, klass)
    r = client.get(f"/api/posts/{t.id}", headers=teacher_headers)
    assert _reply(r.json(), e.id)["my_review"] is not None


def test_a_classmate_sees_nothing(client, db, teacher, teacher_headers, student2_headers, student, klass, enrolled):
    t, e = _graded_entrega(client, db, teacher, teacher_headers, student, klass)
    r = client.get(f"/api/posts/{t.id}", headers=student2_headers)
    assert _reply(r.json(), e.id)["my_review"] is None


def test_veto_reason_is_private_to_the_author(client, db, teacher_headers, auth_headers, student2_headers, enrolled):
    pid = client.post("/api/posts", data={"content": "Participé en clase hoy",
                                          "type": "participacion", "taps": "1"},
                      headers=auth_headers).json()["id"]
    client.post(f"/api/posts/{pid}/veto", json={"reason": "no fue en clase"},
                headers=teacher_headers)
    mine = client.get(f"/api/posts/{pid}", headers=auth_headers).json()["post"]
    theirs = client.get(f"/api/posts/{pid}", headers=student2_headers).json()["post"]
    assert mine["veto_reason"] == "no fue en clase"
    assert theirs["veto_reason"] is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_review_privacy.py -v`
Expected: FAIL — `KeyError: 'my_review'`.

- [ ] **Step 3: Extend the schema**

In `backend/app/schemas.py`, add to `PostOut`:

```python
    my_review: Optional[ReviewOut] = None
    veto_reason: Optional[str] = None
```

`ReviewOut` must be defined above `PostOut` in the file.

- [ ] **Step 4: Implement the visibility rule**

In `backend/app/routers/posts.py`, change `serialize_post`:

```python
def serialize_post(post: Post, liked_ids: Set[int], *, viewer: Optional[User] = None,
                   review_by_post: Optional[dict] = None) -> PostOut:
    removed = post.status != "active"
    # A score, its feedback and a veto reason belong to the student who wrote the
    # post. Classmates read the same thread, so this is withheld server-side.
    private = viewer is not None and (
        viewer.id == post.author_id or viewer.role == "teacher")
    review = (review_by_post or {}).get(post.id) if private else None
    return PostOut(
        ...
        my_review=ReviewOut.model_validate(review) if review is not None else None,
        veto_reason=post.veto_reason if private else None,
    )
```

Keep every existing field; only the signature and those two lines are new. Import `ReviewOut` from `app.schemas`.

In `get_thread`, build the lookup and pass it through:

```python
    entrega_ids = [r.id for r in replies if r.is_entrega]
    review_by_post = {}
    if entrega_ids:
        for rv in db.query(Review).filter(Review.entrega_post_id.in_(entrega_ids)).all():
            review_by_post[rv.entrega_post_id] = rv
    return {"post": serialize_post(post, liked, viewer=user),
            "replies": [serialize_post(r, liked, viewer=user,
                                       review_by_post=review_by_post) for r in replies]}
```

Import `Review` in `posts.py`. In `get_feed`, pass `viewer=user` only — the feed shows roots, which are never entregas:

```python
    return {"items": [serialize_post(p, liked, viewer=user) for p in posts],
            "next_cursor": next_cursor}
```

- [ ] **Step 5: Run the full suite**

Run: `cd backend && ../venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/posts.py backend/app/schemas.py backend/tests/test_review_privacy.py
git commit -m "feat(backend): scores, feedback and veto reasons are private to their author"
```

---

### Task 10: Frontend types, strings and the review client

**Files:**
- Modify: `frontend/src/lib/types.ts`, `frontend/src/strings/es.ts`
- Create: `frontend/src/lib/review.ts`, `frontend/src/lib/review.test.ts`

**Interfaces:**
- Consumes: the endpoints from Tasks 5–8.
- Produces: types `Review`, `EntregaRow`, `EntregaGroup`, `ExamenRoster`, `ParticipacionRow`; functions `saveReview(input: ReviewInput): Promise<Review>`, `markGraded(postId: number, graded: boolean): Promise<{graded_at: string | null}>`, `setVeto(postId: number, vetoed: boolean, reason?: string)`, and `scoreRange(itemType: "tarea" | "examen"): [number, number]`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/lib/review.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { isScoreValid, scoreRange } from "./review";

describe("scoreRange", () => {
  it("uses 0-100 for a tarea and 1-10 for an examen", () => {
    expect(scoreRange("tarea")).toEqual([0, 100]);
    expect(scoreRange("examen")).toEqual([1, 10]);
  });
});

describe("isScoreValid", () => {
  it("accepts the endpoints of each scale", () => {
    expect(isScoreValid(0, "tarea")).toBe(true);
    expect(isScoreValid(100, "tarea")).toBe(true);
    expect(isScoreValid(1, "examen")).toBe(true);
    expect(isScoreValid(10, "examen")).toBe(true);
  });

  it("rejects a tarea score above 100 and an examen score above 10", () => {
    expect(isScoreValid(101, "tarea")).toBe(false);
    expect(isScoreValid(85, "examen")).toBe(false);
  });

  it("rejects NaN and empty input", () => {
    expect(isScoreValid(Number.NaN, "tarea")).toBe(false);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/review.test.ts`
Expected: FAIL — cannot resolve `./review`.

- [ ] **Step 3: Implement the client**

Create `frontend/src/lib/review.ts`:

```ts
import { api } from "@/lib/api";
import type { Review } from "@/lib/types";

export type ItemType = "tarea" | "examen";

/** A tarea is scored 0–100, an examen 1–10. Never mix the two. */
export function scoreRange(itemType: ItemType): [number, number] {
  return itemType === "examen" ? [1, 10] : [0, 100];
}

export function isScoreValid(score: number, itemType: ItemType): boolean {
  if (!Number.isFinite(score)) return false;
  const [low, high] = scoreRange(itemType);
  return score >= low && score <= high;
}

export interface ReviewInput {
  item_post_id: number;
  student_id: number;
  entrega_post_id?: number | null;
  score?: number | null;
  feedback?: string | null;
}

export function saveReview(input: ReviewInput) {
  return api<Review>("/api/reviews", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function markGraded(postId: number, graded: boolean) {
  return api<{ graded_at: string | null }>(`/api/posts/${postId}/graded`, {
    method: graded ? "POST" : "DELETE",
  });
}

export function setVeto(postId: number, vetoed: boolean, reason?: string) {
  return api<{ status: string; veto_reason: string | null }>(
    `/api/posts/${postId}/veto`,
    vetoed
      ? { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: reason ?? null }) }
      : { method: "DELETE" },
  );
}
```

- [ ] **Step 4: Add the types**

In `frontend/src/lib/types.ts`, extend `Post` and add the new interfaces:

```ts
// inside Post
  examen_mode: "paper" | "digital" | null;
  graded_at: string | null;
  my_review: Review | null;
  veto_reason: string | null;

export interface Review {
  id: number;
  item_post_id: number;
  student_id: number;
  entrega_post_id: number | null;
  score: number | null;
  auto_score: number | null;
  feedback: string | null;
  updated_at: string | null;
}

export interface QueueStudent {
  id: number;
  username: string | null;
  name: string;
}

export interface EntregaRow {
  student: QueueStudent;
  entrega_post_id: number;
  created_at: string;
  auto_score: number | null;
  reviewed: boolean;
  score: number | null;
}

export interface EntregaGroup {
  tarea: { id: number; content: string; due_date: string | null };
  pending: number;
  entregas: EntregaRow[];
}

export interface ExamenListItem {
  id: number;
  content: string;
  examen_mode: "paper" | "digital";
  graded_at: string | null;
  created_at: string;
}

export interface ExamenRoster {
  examen: { id: number; content: string; examen_mode: "paper" | "digital";
            graded_at: string | null };
  rows: { student: QueueStudent; entrega_post_id: number | null; score: number | null }[];
}

export interface ParticipacionRow {
  post_id: number;
  student: QueueStudent;
  content: string;
  taps: number | null;
  points: number;
  vetoed: boolean;
  veto_reason: string | null;
  created_at: string;
}
```

Update the `post()` helper in `frontend/src/lib/feed.test.ts` with the new non-optional fields (`examen_mode: null, graded_at: null, my_review: null, veto_reason: null`) so the existing tests still typecheck.

- [ ] **Step 5: Add the strings**

In `frontend/src/strings/es.ts`, add a `revisar` section and extend `compose` and `post`. All values are placeholders for Mario:

```ts
  revisar: {
    title: "Revisar",
    tabEntregas: "Entregas",
    tabExamenes: "Exámenes",
    tabParticipaciones: "Participaciones",
    pending: "{n} sin abrir",
    empty: "Nada por revisar",
    autoScore: "Automático {n}",
    saveAndNext: "Guardar y siguiente",
    save: "Guardar",
    feedbackLabel: "Comentario para el alumno",
    scoreLabel: "Calificación",
    scoreInvalid: "La calificación debe estar entre {low} y {high}",
    markGraded: "Marcar como calificado",
    unmarkGraded: "Quitar calificado",
    markGradedWarning: "{n} alumnos sin calificación contarán como 0.",
    graded: "Calificado",
    veto: "Vetar",
    unveto: "Quitar veto",
    vetoReasonLabel: "Motivo (opcional)",
    vetoed: "Vetada",
    saveError: "No se pudo guardar",
  },
```

Add to `compose`: `modeExamen: "Examen"`, `examenModeLabel: "Modalidad"`, `examenPaper: "En papel"`, `examenDigital: "Entrega digital"`, `examenPlaceholder: "¿Qué examen es y qué cubre?"`.

Add to `post`: `scoreBadge: "Calificación {n}"`, `feedbackFrom: "Comentario del profesor"`, `vetoedNotice: "Esta participación no cuenta"`, `examenBadge: "Examen"`.

- [ ] **Step 6: Verify and commit**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run lint`
Expected: all pass.

```bash
git add frontend/src/lib frontend/src/strings/es.ts
git commit -m "feat(frontend): review types, strings and API client"
```

---

### Task 11: `/revisar` — the Entregas tab

**Files:**
- Create: `frontend/src/pages/Revisar.tsx`, `frontend/src/components/ReviewSheet.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/components/Shell.tsx`
- Test: manual (see step 5)

**Interfaces:**
- Consumes: `GET /api/review/entregas`, `saveReview`, `EntregaGroup`.
- Produces: route `/revisar`; `<ReviewSheet item={{id, type}} student={QueueStudent} entregaPostId={number|null} autoScore={number|null} initialScore={number|null} initialFeedback={string} onSaved={() => void} onClose={() => void} />` — reused by Tasks 12 and 14.

- [ ] **Step 1: Build the shared sheet**

Create `frontend/src/components/ReviewSheet.tsx`:

```tsx
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { isScoreValid, saveReview, scoreRange, type ItemType } from "@/lib/review";
import { useToast } from "@/components/Toaster";
import { es } from "@/strings/es";
import type { QueueStudent } from "@/lib/types";

export default function ReviewSheet({
  item, student, entregaPostId, autoScore, initialScore, initialFeedback, onSaved, onClose,
}: {
  item: { id: number; type: ItemType };
  student: QueueStudent;
  entregaPostId: number | null;
  autoScore: number | null;
  initialScore: number | null;
  initialFeedback: string;
  onSaved: () => void;
  onClose: () => void;
}) {
  const toast = useToast();
  const [low, high] = scoreRange(item.type);
  const [score, setScore] = useState<string>(
    String(initialScore ?? autoScore ?? ""),
  );
  const [feedback, setFeedback] = useState(initialFeedback);
  const value = Number(score);
  const valid = score !== "" && isScoreValid(value, item.type);

  const save = useMutation({
    mutationFn: () =>
      saveReview({
        item_post_id: item.id,
        student_id: student.id,
        entrega_post_id: entregaPostId,
        score: value,
        feedback: feedback.trim() || null,
      }),
    onSuccess: () => { onSaved(); onClose(); },
    onError: () => toast.show(es.revisar.saveError),
  });

  return (
    <div className="fixed inset-0 z-40 flex items-end bg-black/40" onClick={onClose}>
      <div
        className="max-h-[85dvh] w-full overflow-y-auto rounded-t-2xl bg-background p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="font-bold">@{student.username ?? student.name}</p>
        {autoScore != null && (
          <p className="text-sm text-muted-foreground">
            {es.revisar.autoScore.replace("{n}", String(autoScore))}
          </p>
        )}
        <label className="mt-3 block text-sm">
          {es.revisar.scoreLabel}
          <input
            type="number"
            inputMode="numeric"
            min={low}
            max={high}
            className="ml-2 w-24 rounded-md border px-2 py-1"
            value={score}
            onChange={(e) => setScore(e.target.value)}
          />
        </label>
        {!valid && score !== "" && (
          <p className="mt-1 text-xs text-destructive">
            {es.revisar.scoreInvalid.replace("{low}", String(low)).replace("{high}", String(high))}
          </p>
        )}
        <label className="mt-3 block text-sm">
          {es.revisar.feedbackLabel}
          <textarea
            className="mt-1 min-h-24 w-full rounded-lg border p-2"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
          />
        </label>
        <button
          disabled={!valid || save.isPending}
          onClick={() => save.mutate()}
          className="mt-3 w-full rounded-full bg-primary py-2 text-primary-foreground disabled:opacity-50"
        >
          {es.revisar.save}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Build the page with its first tab**

Create `frontend/src/pages/Revisar.tsx`:

```tsx
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import ReviewSheet from "@/components/ReviewSheet";
import { FeedSkeleton } from "@/components/Skeletons";
import { es } from "@/strings/es";
import type { EntregaGroup, EntregaRow, MyClasses, QueueStudent } from "@/lib/types";

type Tab = "entregas" | "examenes" | "participaciones";

export default function Revisar() {
  const [tab, setTab] = useState<Tab>("entregas");
  const [classId, setClassId] = useState<number | null>(null);
  const qc = useQueryClient();

  const mine = useQuery({
    queryKey: ["classes-mine"],
    queryFn: () => api<MyClasses>("/api/classes/mine"),
  });
  const teaching = mine.data?.teaching ?? [];
  const activeClass = classId ?? teaching[0]?.id ?? null;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="font-bold">{es.revisar.title}</h1>

      {teaching.length > 1 && (
        <select
          className="rounded-md border px-2 py-1 text-sm"
          value={activeClass ?? ""}
          onChange={(e) => setClassId(Number(e.target.value))}
        >
          {teaching.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
        </select>
      )}

      <div className="flex gap-2 overflow-x-auto">
        {(["entregas", "examenes", "participaciones"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`whitespace-nowrap rounded-full px-3 py-1 text-sm ${tab === t ? "bg-primary text-primary-foreground" : "border"}`}
          >
            {t === "entregas" ? es.revisar.tabEntregas
              : t === "examenes" ? es.revisar.tabExamenes
              : es.revisar.tabParticipaciones}
          </button>
        ))}
      </div>

      {activeClass != null && tab === "entregas" && (
        <EntregasTab classId={activeClass} onSaved={() => {
          void qc.invalidateQueries({ queryKey: ["review-entregas"] });
        }} />
      )}
    </main>
  );
}

function EntregasTab({ classId, onSaved }: { classId: number; onSaved: () => void }) {
  const [open, setOpen] = useState<{ tareaId: number; row: EntregaRow } | null>(null);
  const q = useQuery({
    queryKey: ["review-entregas", classId],
    queryFn: () => api<{ groups: EntregaGroup[] }>(
      `/api/review/entregas?class_id=${classId}&status=unopened`),
  });

  if (q.isPending) return <FeedSkeleton />;
  if (q.isError) return <p className="text-muted-foreground">{es.feed.error}</p>;
  if (q.data.groups.length === 0)
    return <p className="text-center text-muted-foreground">{es.revisar.empty}</p>;

  return (
    <div className="flex flex-col gap-4">
      {q.data.groups.map((g) => (
        <section key={g.tarea.id}>
          <h2 className="text-sm font-bold">
            📌 {g.tarea.content.slice(0, 60)}
            <span className="ml-2 font-normal text-muted-foreground">
              {es.revisar.pending.replace("{n}", String(g.pending))}
            </span>
          </h2>
          <ul className="mt-1 divide-y rounded-lg border">
            {g.entregas.map((row) => (
              <li key={row.entrega_post_id}>
                <button
                  className="flex w-full items-center justify-between px-3 py-3 text-left"
                  onClick={() => setOpen({ tareaId: g.tarea.id, row })}
                >
                  <span>@{row.student.username ?? row.student.name}</span>
                  <span className="text-sm text-muted-foreground">
                    {row.auto_score != null
                      ? es.revisar.autoScore.replace("{n}", String(row.auto_score))
                      : ""}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
      {open && (
        <ReviewSheet
          item={{ id: open.tareaId, type: "tarea" }}
          student={open.row.student as QueueStudent}
          entregaPostId={open.row.entrega_post_id}
          autoScore={open.row.auto_score}
          initialScore={open.row.score}
          initialFeedback=""
          onSaved={onSaved}
          onClose={() => setOpen(null)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 3: Route and navigation**

In `frontend/src/App.tsx`, add inside the authenticated routes, following the exact pattern of the `/clases` route:

```tsx
            <Route
              path="/revisar"
              element={<RequireAuth><Shell><Revisar /></Shell></RequireAuth>}
            />
```

Import `Revisar` at the top. In `frontend/src/components/Shell.tsx`, add a teacher-only link inside the drawer nav, right after the `/clases` link:

```tsx
            {user?.role === "teacher" && (
              <Link to="/revisar" className="rounded-md px-3 py-2 hover:bg-accent" onClick={() => setMenuOpen(false)}>
                {es.revisar.title}
              </Link>
            )}
```

- [ ] **Step 4: Verify**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run`
Expected: all pass.

- [ ] **Step 5: Check it by hand**

Run the app (`npm run dev` in `frontend/`, `../venv/bin/python -m uvicorn app.main:app --reload` in `backend/`), log in as the teacher, publish a tarea, reply as a student with the entrega toggle on, then open `/revisar` at a 390 px viewport. Confirm the entrega appears, the sheet opens, saving a score removes it from the list, and the student's grade chip reflects the new score.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Revisar.tsx frontend/src/components/ReviewSheet.tsx frontend/src/App.tsx frontend/src/components/Shell.tsx
git commit -m "feat(frontend): Revisar page with the entregas queue"
```

---

### Task 12: Revisar — the Exámenes tab

**Files:**
- Modify: `frontend/src/pages/Revisar.tsx`
- Create: `frontend/src/components/ExamenRoster.tsx`

**Interfaces:**
- Consumes: `GET /api/review/examenes/{id}`, `markGraded`, `saveReview`, `ExamenRoster`.
- Produces: `<ExamenRosterPanel examenId={number} onClose={() => void} />`.

- [ ] **Step 1: Build the roster**

Create `frontend/src/components/ExamenRoster.tsx`:

```tsx
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { isScoreValid, markGraded, saveReview } from "@/lib/review";
import { useToast } from "@/components/Toaster";
import { es } from "@/strings/es";
import type { ExamenRoster } from "@/lib/types";

export default function ExamenRosterPanel({ examenId }: { examenId: number }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [draft, setDraft] = useState<Record<number, string>>({});

  const q = useQuery({
    queryKey: ["examen-roster", examenId],
    queryFn: () => api<ExamenRoster>(`/api/review/examenes/${examenId}`),
  });

  const save = useMutation({
    mutationFn: ({ studentId, score }: { studentId: number; score: number }) =>
      saveReview({ item_post_id: examenId, student_id: studentId, score }),
    onError: () => toast.show(es.revisar.saveError),
  });

  const flip = useMutation({
    mutationFn: (graded: boolean) => markGraded(examenId, graded),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["examen-roster", examenId] });
      void qc.invalidateQueries({ queryKey: ["grade"] });
    },
    onError: () => toast.show(es.revisar.saveError),
  });

  if (q.isPending) return <p className="text-muted-foreground">…</p>;
  if (q.isError) return <p className="text-muted-foreground">{es.feed.error}</p>;

  const { examen, rows } = q.data;
  const missing = rows.filter((r) => r.score == null).length;

  function commit(studentId: number, raw: string) {
    const score = Number(raw);
    if (raw === "" || !isScoreValid(score, "examen")) return;
    save.mutate({ studentId, score });
  }

  return (
    <div className="flex flex-col gap-3">
      <ul className="divide-y rounded-lg border">
        {rows.map((r) => (
          <li key={r.student.id} className="flex items-center justify-between px-3 py-2">
            <span>@{r.student.username ?? r.student.name}</span>
            <input
              type="number"
              inputMode="numeric"
              min={1}
              max={10}
              className="w-20 rounded-md border px-2 py-1 text-right"
              value={draft[r.student.id] ?? (r.score != null ? String(r.score) : "")}
              onChange={(e) => setDraft({ ...draft, [r.student.id]: e.target.value })}
              onBlur={(e) => commit(r.student.id, e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              }}
            />
          </li>
        ))}
      </ul>

      {examen.graded_at == null && missing > 0 && (
        <p className="text-xs text-muted-foreground">
          {es.revisar.markGradedWarning.replace("{n}", String(missing))}
        </p>
      )}
      <button
        onClick={() => flip.mutate(examen.graded_at == null)}
        className="rounded-full border px-4 py-2 text-sm"
      >
        {examen.graded_at == null ? es.revisar.markGraded : es.revisar.unmarkGraded}
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Wire the tab**

In `frontend/src/pages/Revisar.tsx`, add the tab body below the entregas one:

```tsx
      {activeClass != null && tab === "examenes" && (
        <ExamenesTab classId={activeClass} />
      )}
```

And the component, which lists the class's exámenes and drills into one:

```tsx
function ExamenesTab({ classId }: { classId: number }) {
  const [openId, setOpenId] = useState<number | null>(null);
  const q = useQuery({
    queryKey: ["review-examenes", classId],
    queryFn: () => api<{ items: ExamenListItem[] }>(
      `/api/review/examenes?class_id=${classId}`),
    select: (data) => data.items,
  });

  if (q.isPending) return <FeedSkeleton />;
  if (!q.data || q.data.length === 0)
    return <p className="text-center text-muted-foreground">{es.revisar.empty}</p>;
  if (openId != null)
    return (
      <div className="flex flex-col gap-2">
        <button className="self-start text-sm text-muted-foreground"
                onClick={() => setOpenId(null)}>←</button>
        <ExamenRosterPanel examenId={openId} />
      </div>
    );

  return (
    <ul className="divide-y rounded-lg border">
      {q.data.map((x) => (
        <li key={x.id}>
          <button className="flex w-full items-center justify-between px-3 py-3 text-left"
                  onClick={() => setOpenId(x.id)}>
            <span>📝 {x.content.slice(0, 50)}</span>
            <span className="text-xs text-muted-foreground">
              {x.graded_at ? es.revisar.graded : ""}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
```

Import `ExamenRosterPanel` and `ExamenListItem` at the top of the file.

- [ ] **Step 3: Verify**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run`
Expected: all pass.

- [ ] **Step 4: Check it by hand**

As the teacher, create a paper examen, open `/revisar` → Exámenes, type scores for two students, press Enter on each, reload the page and confirm the scores persisted. Flip "Marcar como calificado" and confirm a student's grade chip now shows an exámenes rubro instead of `—`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Revisar.tsx frontend/src/components/ExamenRoster.tsx
git commit -m "feat(frontend): examen roster with score entry and the calificado flip"
```

---

### Task 13: Revisar — the Participaciones tab

**Files:**
- Modify: `frontend/src/pages/Revisar.tsx`

**Interfaces:**
- Consumes: `GET /api/review/participaciones`, `setVeto`, `ParticipacionRow`.
- Produces: the third tab body.

- [ ] **Step 1: Implement the tab**

Add to `frontend/src/pages/Revisar.tsx`:

```tsx
      {activeClass != null && tab === "participaciones" && (
        <ParticipacionesTab classId={activeClass} />
      )}
```

```tsx
function ParticipacionesTab({ classId }: { classId: number }) {
  const qc = useQueryClient();
  const toast = useToast();
  const key = ["review-participaciones", classId];
  const q = useQuery({
    queryKey: key,
    queryFn: () => api<{ items: ParticipacionRow[] }>(
      `/api/review/participaciones?class_id=${classId}`),
  });

  const toggle = useMutation({
    mutationFn: ({ postId, vetoed }: { postId: number; vetoed: boolean }) =>
      setVeto(postId, vetoed),
    onMutate: async ({ postId, vetoed }) => {
      await qc.cancelQueries({ queryKey: key });
      const prev = qc.getQueryData<{ items: ParticipacionRow[] }>(key);
      qc.setQueryData<{ items: ParticipacionRow[] }>(key, (old) =>
        old ? { items: old.items.map((i) =>
          i.post_id === postId ? { ...i, vetoed } : i) } : old);
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(key, ctx.prev);   // visible rollback
      toast.show(es.revisar.saveError);
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: key });
      void qc.invalidateQueries({ queryKey: ["grade"] });
    },
  });

  if (q.isPending) return <FeedSkeleton />;
  if (q.isError) return <p className="text-muted-foreground">{es.feed.error}</p>;
  if (q.data.items.length === 0)
    return <p className="text-center text-muted-foreground">{es.revisar.empty}</p>;

  return (
    <ul className="divide-y rounded-lg border">
      {q.data.items.map((i) => (
        <li key={i.post_id} className="flex items-start justify-between gap-3 px-3 py-3">
          <div className="min-w-0">
            <p className="text-sm font-medium">
              @{i.student.username ?? i.student.name}
              <span className="ml-2 font-normal text-muted-foreground">
                ×{i.taps ?? 0} · {i.points}
              </span>
            </p>
            <p className="truncate text-sm text-muted-foreground">{i.content}</p>
          </div>
          <button
            onClick={() => toggle.mutate({ postId: i.post_id, vetoed: !i.vetoed })}
            className={`shrink-0 rounded-full px-3 py-1 text-xs ${i.vetoed ? "border" : "bg-destructive text-destructive-foreground"}`}
          >
            {i.vetoed ? es.revisar.unveto : es.revisar.veto}
          </button>
        </li>
      ))}
    </ul>
  );
}
```

Import `useMutation`, `setVeto`, `useToast` and `ParticipacionRow` at the top of the file.

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run`
Expected: all pass.

- [ ] **Step 3: Check it by hand**

Publish a participación as a student, veto it from Revisar, confirm the student's grade chip drops by the tap value, un-veto it and confirm it comes back. Kill the backend and tap veto to confirm the row visibly rolls back and a toast appears.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Revisar.tsx
git commit -m "feat(frontend): participaciones tab with optimistic veto"
```

---

### Task 14: Grading inline in the thread, and what the student sees

**Files:**
- Modify: `frontend/src/pages/Thread.tsx`, `frontend/src/components/PostCard.tsx`

**Interfaces:**
- Consumes: `PostOut.my_review`, `PostOut.veto_reason`, `ReviewSheet` from Task 11.
- Produces: no new exports.

- [ ] **Step 1: Show the score to whoever may see it**

In `frontend/src/components/PostCard.tsx`, add after the entrega badge block:

```tsx
        {post.my_review?.score != null && !removed && (
          <span className="mt-1 inline-block rounded-full bg-sky-500/15 px-2 py-0.5 text-xs font-medium text-sky-700">
            {es.post.scoreBadge.replace("{n}", String(post.my_review.score))}
          </span>
        )}
        {post.my_review?.feedback && !removed && (
          <p className="mt-1 rounded-lg bg-muted p-2 text-xs">
            <span className="font-medium">{es.post.feedbackFrom}: </span>
            {post.my_review.feedback}
          </p>
        )}
        {post.status === "vetoed" && post.veto_reason && (
          <p className="mt-1 text-xs text-destructive">
            {es.post.vetoedNotice} · {post.veto_reason}
          </p>
        )}
        {post.type === "examen" && !removed && (
          <span className="mt-1 inline-block rounded-full bg-violet-500/15 px-2 py-0.5 text-xs font-medium text-violet-700">
            📝 {es.post.examenBadge}
          </span>
        )}
```

The server already withholds `my_review` and `veto_reason` from everyone but the author and the teacher, so no role check is needed here.

- [ ] **Step 2: Let the teacher grade from the thread**

In `frontend/src/pages/Thread.tsx`, add state and the sheet:

```tsx
  const [grading, setGrading] = useState<Post | null>(null);
```

Render a grade button on entrega replies when the viewer is the teacher, inside the reply block where the "↩ responder" button already lives:

```tsx
      {user?.role === "teacher" && p.is_entrega && (
        <button className="mb-2 ml-4 text-xs text-muted-foreground"
                onClick={() => setGrading(p)}>
          ✎ {es.revisar.scoreLabel}
        </button>
      )}
```

And at the end of the component's JSX:

```tsx
      {grading && (
        <ReviewSheet
          item={{ id: post.id, type: post.type === "examen" ? "examen" : "tarea" }}
          student={{ id: grading.author.id, username: grading.author.username,
                     name: grading.author.name }}
          entregaPostId={grading.id}
          autoScore={post.due_date
            ? latenessTier(new Date(grading.created_at), new Date(post.due_date)).pct
            : null}
          initialScore={grading.my_review?.score ?? null}
          initialFeedback={grading.my_review?.feedback ?? ""}
          onSaved={() => {
            void qc.invalidateQueries({ queryKey: ["thread", id] });
            void qc.invalidateQueries({ queryKey: ["grade"] });
          }}
          onClose={() => setGrading(null)}
        />
      )}
```

Import `ReviewSheet`. `latenessTier` is already imported in this file.

- [ ] **Step 3: Verify**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run`
Expected: all pass.

- [ ] **Step 4: Check it by hand**

Open a tarea thread as the teacher, grade an entrega inline, then open the same thread as its author and confirm the score and feedback appear. Open it as a *different* student and confirm neither does.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Thread.tsx frontend/src/components/PostCard.tsx
git commit -m "feat(frontend): inline grading in the thread, private scores for the author"
```

---

### Task 15: Composer — examen mode

**Files:**
- Modify: `frontend/src/pages/Compose.tsx`

**Interfaces:**
- Consumes: `POST /api/posts` with `type=examen` and `examen_mode` from Task 5.
- Produces: no new exports.

- [ ] **Step 1: Extend the mode state**

In `frontend/src/pages/Compose.tsx`:

```tsx
  const [mode, setMode] = useState<"regular" | "participacion" | "tarea" | "examen">("regular");
  const [examenMode, setExamenMode] = useState<"paper" | "digital">("paper");
```

Extend the teacher mode selector to three options:

```tsx
          {(["regular", "tarea", "examen"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`rounded-full px-3 py-1 text-sm ${mode === m ? "bg-primary text-primary-foreground" : "border"}`}
            >
              {m === "regular" ? es.compose.modeRegular
                : m === "tarea" ? `📌 ${es.compose.modeTarea}`
                : `📝 ${es.compose.modeExamen}`}
            </button>
          ))}
```

Add the modality picker, shown only in examen mode:

```tsx
      {mode === "examen" && (
        <label className="text-sm">
          {es.compose.examenModeLabel}
          <select
            className="ml-2 rounded-md border px-2 py-1"
            value={examenMode}
            onChange={(e) => setExamenMode(e.target.value as "paper" | "digital")}
          >
            <option value="paper">{es.compose.examenPaper}</option>
            <option value="digital">{es.compose.examenDigital}</option>
          </select>
        </label>
      )}
```

Send it in the mutation, next to the existing `due_date` line:

```tsx
      if (mode === "examen") fd.set("examen_mode", examenMode);
```

Extend `needsClass` so an examen also requires a class:

```tsx
  const needsClass = (mode === "tarea" || mode === "examen") && classId == null;
```

And add the examen placeholder to the textarea ternary, following the existing pattern.

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run`
Expected: all pass.

- [ ] **Step 3: Check it by hand**

As the teacher, create one paper examen and one digital examen. Confirm both appear in the feed with the examen badge, and that the digital one accepts an "Es mi entrega" reply while the paper one is simply a post.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Compose.tsx
git commit -m "feat(frontend): examen mode in the composer, paper or digital"
```

---

### Task 16: Close out the phase

**Files:**
- Modify: `planning/changelog.md`, `planning/roadmap.md`, `planning/bugs.md`

- [ ] **Step 1: Run everything**

```bash
cd backend && ../venv/bin/python -m pytest -q
cd ../frontend && npx vitest run && npx tsc --noEmit && npm run lint && npm run build
```

Expected: all green. Record the actual test counts — they go in the changelog.

- [ ] **Step 2: Write the changelog entry**

Add a dated entry at the top of `planning/changelog.md` in Spanish, following the shape of the 2026-07-30 entry: what shipped, the decisions a reader would otherwise have to reverse-engineer (why an examen needs `graded_at`, why a review can go stale, why deletion stopped revoking points), what was deferred to 2b-2, and the real test counts.

- [ ] **Step 3: Update the roadmap and bugs**

Tick the 2b-1 line in `planning/roadmap.md`. In `planning/bugs.md`, confirm bug 2 (deleting your latest entrega loses the tarea) is still open and still accurate after this phase's changes to the delete path — if Task 7 changed its reproduction steps, rewrite them.

- [ ] **Step 4: Commit**

```bash
git add planning/
git commit -m "docs: close out Phase 2b-1"
```

---

## Notes for the reviewer

- The engine is the most-tested code in the repo and must stay that way. Tasks 2–4 are where a subtle mistake costs a real student real points.
- `PUT /api/reviews` is the only write path for a score. If a later task needs to write one, it calls that endpoint rather than touching `Review` directly.
- Task 7 changes existing behaviour: deletion no longer revokes points. That is the documented rule (`deleted ≠ vetoed`), not a regression.
- Nothing in this phase writes attendance. The faltas term stays at zero until Phase 3.
