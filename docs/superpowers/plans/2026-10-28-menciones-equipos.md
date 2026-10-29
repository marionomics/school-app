# Menciones y entregas en equipo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Students can `@` each other anywhere; an `@` of up to 2 active classmates in a submission makes it a team submission whose single grade counts for every member.

**Architecture:** A new `post_mentions` table stores every parsed `@username` (`social`) and, for submissions, the team decision (`team`), made once at publish. A new `app/services/submissions.py` owns "which submission counts for this student" (own ∪ live team, newest wins); `grades._counting_entrega`, `grades.examen_submission` and `grades.counting_review` delegate to it, so every caller follows. The teacher's review lives on the submission's author; members read it. The two places that inline the rule (`feed_query.teacher_pending`, the thread) are updated and pinned by agreement tests.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest (CI on PostgreSQL); React + Vite + Tailwind, TanStack Query, vitest; shadcn `base-sera` on `@base-ui/react`.

**Spec:** `docs/superpowers/specs/2026-10-28-menciones-equipos-design.md` — read it first; this plan argues from it.

## Global Constraints

- Grades are computed, never stored. No review is ever copied to a team member; a member's grade *is* the author's review of the counting submission.
- Never DELETE a mention row. Removing a member sets `removed_at`/`removed_by`; restoring clears them.
- The team decision (`kind`) is written once at publish and never recomputed.
- Team size: author + at most **2** members (`MAX_TEAM = 2`).
- Only `active` enrollments form teams — ghost 👻 and polizón 🥷 never; if the author is not `active` in the item's class, no team forms.
- Username pattern: `[A-Za-z0-9_]{3,20}`, stored lowercase; an `@` preceded by a letter, digit or `_` is not a mention (emails).
- Every username or avatar in the UI goes through `UserLink` (`plain` on editing surfaces: grading sheet, roster, reply composer).
- Every user-facing string is a placeholder in `frontend/src/strings/es.ts` (Spanish, tú — never usted). Mario writes final copy.
- Use preset components (`npx shadcn add …`); never restyle a primitive. Icons from `@remixicon/react`; no emoji UI.
- One control per line in any form.
- Backend tests: `cd backend && python -m pytest -q` (activate `backend/.venv` or the repo `.venv`). Frontend: `cd frontend && npx tsc -b && npx vitest run && npx eslint src`.
- Implementers commit, never push. The controller pushes after a clean review (every push reaches students).

## Review Focus

1. **`@` that is not a mention** — `pedro@gmail.com`, a lone `@`, `@ab` (too short) must create no row and render as plain text. Pinned in Task 2 and Task 8.
2. **Uppercase `@Pedro`** must resolve to `pedro`, server and client. Pinned in Task 2 (server) and Task 8 (client parse).
3. **`_` in a search term** (`a_b`) must match literally, not as a SQL wildcard. Pinned in Task 5.
4. **Team author becomes ghost after submitting** while members stay active — the entrega still counts for members, the teacher can still grade it from a member's row, and it still shows as pending. Pinned in Task 7.
5. **Old iOS Safari** (< 16.4) throws on regex lookbehind at module load, which would blank the app for some students. The client parser must not use `(?<`. Pinned in Task 8.

---

### Task 1: `post_mentions` table

**Files:**
- Modify: `backend/app/models.py` (add `PostMention`, `Post.mentions`)
- Create: `backend/alembic/versions/f1a9c3e7b2d5_post_mentions.py`
- Test: `backend/tests/test_mentions_model.py`

**Interfaces:**
- Produces: `PostMention` model (`id, post_id, user_id, kind, created_at, removed_at, removed_by`, relationship `user`), `Post.mentions` (list, `lazy="selectin"`, ordered by id).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_mentions_model.py
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Post, PostMention


def test_post_loads_its_mentions_in_order(db, student, teacher):
    p = Post(author_id=student.id, content="hola @profe")
    db.add(p)
    db.flush()
    db.add(PostMention(post_id=p.id, user_id=teacher.id, kind="social"))
    db.commit()
    db.expire_all()
    p = db.get(Post, p.id)
    assert [(m.user.id, m.kind, m.removed_at) for m in p.mentions] == [
        (teacher.id, "social", None)]


def test_one_row_per_post_and_user(db, student, teacher):
    p = Post(author_id=student.id, content="x")
    db.add(p)
    db.flush()
    db.add(PostMention(post_id=p.id, user_id=teacher.id, kind="social"))
    db.add(PostMention(post_id=p.id, user_id=teacher.id, kind="team"))
    with pytest.raises(IntegrityError):
        db.commit()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_mentions_model.py -q`
Expected: FAIL — `ImportError: cannot import name 'PostMention'`.

- [ ] **Step 3: Add the model**

In `backend/app/models.py`, after `class Post`, add:

```python
class PostMention(Base):
    """An @username in a post. `kind` is decided once, at publish: 'team' only
    for a submission naming an eligible classmate (spec 2026-10-28), else
    'social'. Never deleted — the teacher removing a team member sets
    removed_at, like the ledger's revocation flag."""
    __tablename__ = "post_mentions"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_mention_post_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10))   # social|team
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    removed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    removed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="joined")
```

And inside `class Post`, after `attachments`:

```python
    # selectin: the feed serializes mentions on every card; one batched query
    # per page instead of one per post.
    mentions: Mapped[List["PostMention"]] = relationship(
        lazy="selectin", order_by="PostMention.id")
```

- [ ] **Step 4: Write the migration**

```python
# backend/alembic/versions/f1a9c3e7b2d5_post_mentions.py
"""post_mentions

Every @username in a post, and for a submission whether it made that person
part of the team (spec 2026-10-28-menciones-equipos). A new table only — no
existing row changes, so it is safe against production data.

Revision ID: f1a9c3e7b2d5
Revises: e5b2c8d1a7f4
Create Date: 2026-10-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f1a9c3e7b2d5"
down_revision: Union[str, Sequence[str], None] = "e5b2c8d1a7f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "post_mentions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(),
                  sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("post_id", "user_id", name="uq_mention_post_user"),
    )
    op.create_index("ix_post_mentions_post_id", "post_mentions", ["post_id"])
    op.create_index("ix_post_mentions_user_id", "post_mentions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_post_mentions_user_id", "post_mentions")
    op.drop_index("ix_post_mentions_post_id", "post_mentions")
    op.drop_table("post_mentions")
```

Before writing it, confirm the head: `cd backend && alembic heads` must print `e5b2c8d1a7f4 (head)`. If it doesn't, set `down_revision` to whatever it prints.

- [ ] **Step 5: Run tests and the migration**

Run: `cd backend && python -m pytest tests/test_mentions_model.py tests/test_migrations.py -q`
Expected: PASS. Then `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` against the local SQLite DB: no errors.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/alembic/versions/f1a9c3e7b2d5_post_mentions.py backend/tests/test_mentions_model.py
git commit -m "feat(mentions): post_mentions table"
```

---

### Task 2: Parsing `@username`

**Files:**
- Create: `backend/app/services/mentions.py`
- Test: `backend/tests/test_mentions_parse.py`

**Interfaces:**
- Produces: `parse_usernames(content: str) -> List[str]` — ordered, unique, lowercase.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_mentions_parse.py
from app.services.mentions import parse_usernames


def test_finds_mentions_in_order_lowercased_and_unique():
    assert parse_usernames("con @Ana y @pedro_2, otra vez @ana") == ["ana", "pedro_2"]


def test_an_email_is_not_a_mention():
    assert parse_usernames("escríbeme a pedro@gmail.com") == []


def test_too_short_lone_or_glued_at_signs_are_not_mentions():
    assert parse_usernames("@ab @ hola@@x a@pedro") == []


def test_mention_at_start_after_punctuation_and_newline():
    assert parse_usernames("@ana\n(@luis) ¡@pedro!") == ["ana", "luis", "pedro"]


def test_more_than_twenty_characters_is_not_a_username():
    assert parse_usernames("@" + "a" * 21) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_mentions_parse.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.mentions'`.

- [ ] **Step 3: Implement**

```python
# backend/app/services/mentions.py
"""@mentions: parsing, and deciding who a submission's team is.

Spec: docs/superpowers/specs/2026-10-28-menciones-equipos-design.md
"""
import re
from typing import List

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
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_mentions_parse.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/mentions.py backend/tests/test_mentions_parse.py
git commit -m "feat(mentions): parse @username"
```

---

### Task 3: Submissions engine — own ∪ live team

The heart of the block. Every grade path asks these functions which submission counts.

**Files:**
- Create: `backend/app/services/submissions.py`
- Modify: `backend/app/services/grades.py` (`_counting_entrega`, `examen_submission`, `counting_review`, `examenes_rubro`)
- Test: `backend/tests/test_teams_engine.py`

**Interfaces:**
- Consumes: `PostMention` (Task 1).
- Produces (in `app.services.submissions`):
  - `own_entrega(db, user_id: int, item_id: int) -> Optional[Post]`
  - `own_submission(db, user_id: int, item: Post) -> Optional[Post]`
  - `live_team_submissions(db, user_id: int, item: Post, entrega_only: bool = False) -> List[Post]`
  - `counting_entrega(db, user_id: int, item_id: int) -> Optional[Post]`
  - `counting_submission(db, user_id: int, item: Post) -> Optional[Post]`
  - `live_team_member_ids(db, post: Post) -> List[int]`
  - `team_of(db, user_id: int, item: Post, ignore_author: Optional[int] = None) -> Optional[Post]`
- `grades._counting_entrega` / `grades.examen_submission` keep their names and signatures; `grades.counting_review` now reads the **submission author's** review.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_teams_engine.py
"""Team submissions in the grade engine (spec 2026-10-28, §2)."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models import Attachment, Enrollment, Post, PostMention, Review, User, utcnow
from app.services.grades import (_counting_entrega, counting_review, examen_submission,
                                 tareas_rubro)
from app.services.submissions import live_team_member_ids, team_of

DUE = datetime(2026, 8, 9, 23, 59, tzinfo=timezone.utc)
AFTER = datetime(2026, 8, 20, tzinfo=timezone.utc)


def _user(db, klass, handle, status="active"):
    u = User(google_id=f"g-{handle}", email=f"{handle}@example.com",
             name=handle.title(), username=handle)
    db.add(u)
    db.flush()
    db.add(Enrollment(user_id=u.id, class_id=klass.id, status=status))
    db.commit()
    return u


def _item(db, teacher, klass, type="tarea"):
    p = Post(author_id=teacher.id, class_id=klass.id, type=type, content="P",
             due_date=DUE if type == "tarea" else None,
             examen_mode="digital" if type == "examen" else None)
    db.add(p)
    db.commit()
    return p


def _sub(db, author, item, at, team=(), is_entrega=True, files=(), status="active"):
    p = Post(author_id=author.id, class_id=item.class_id, parent_id=item.id,
             content="x", is_entrega=is_entrega, created_at=at, status=status)
    db.add(p)
    db.flush()
    for u in team:
        db.add(PostMention(post_id=p.id, user_id=u.id, kind="team"))
    for name in files:
        db.add(Attachment(post_id=p.id, file_key=f"k/{name}", file_name=name,
                          file_size=10, mime_type="application/pdf"))
    db.commit()
    return p


def _team(db, klass):
    return _user(db, klass, "ana"), _user(db, klass, "pedro"), _user(db, klass, "luis")


def test_a_team_entrega_counts_for_every_member(db, teacher, klass):
    ana, pedro, luis = _team(db, klass)
    t = _item(db, teacher, klass)
    e = _sub(db, ana, t, DUE, team=[pedro, luis])
    for u in (ana, pedro, luis):
        assert _counting_entrega(db, u.id, t.id).id == e.id


def test_newer_wins_between_own_and_team(db, teacher, klass):
    ana, pedro, _ = _team(db, klass)
    t = _item(db, teacher, klass)
    draft = _sub(db, pedro, t, DUE - timedelta(hours=3))
    final = _sub(db, ana, t, DUE - timedelta(hours=2), team=[pedro])
    assert _counting_entrega(db, pedro.id, t.id).id == final.id
    mine_again = _sub(db, pedro, t, DUE - timedelta(hours=1))
    assert _counting_entrega(db, pedro.id, t.id).id == mine_again.id
    assert draft.id != mine_again.id


def test_author_replacing_without_tags_drops_the_team(db, teacher, klass):
    ana, pedro, _ = _team(db, klass)
    t = _item(db, teacher, klass)
    own = _sub(db, pedro, t, DUE - timedelta(hours=5))
    _sub(db, ana, t, DUE - timedelta(hours=2), team=[pedro])
    _sub(db, ana, t, DUE - timedelta(hours=1))          # Ana alone now
    assert _counting_entrega(db, pedro.id, t.id).id == own.id


def test_author_replacing_with_tags_carries_the_team(db, teacher, klass):
    ana, pedro, _ = _team(db, klass)
    t = _item(db, teacher, klass)
    _sub(db, ana, t, DUE - timedelta(hours=2), team=[pedro])
    v2 = _sub(db, ana, t, DUE - timedelta(hours=1), team=[pedro])
    assert _counting_entrega(db, pedro.id, t.id).id == v2.id


def test_a_removed_member_falls_back_to_nothing_or_their_own(db, teacher, klass):
    ana, pedro, luis = _team(db, klass)
    t = _item(db, teacher, klass)
    own = _sub(db, luis, t, DUE - timedelta(hours=5))
    e = _sub(db, ana, t, DUE - timedelta(hours=2), team=[pedro, luis])
    for m in e.mentions:
        m.removed_at = utcnow()
    db.commit()
    assert _counting_entrega(db, pedro.id, t.id) is None
    assert _counting_entrega(db, luis.id, t.id).id == own.id
    assert live_team_member_ids(db, e) == []


def test_deleted_or_vetoed_team_entrega_counts_for_nobody(db, teacher, klass):
    for status in ("deleted", "vetoed"):
        t = _item(db, teacher, klass)
        ana = _user(db, klass, f"ana_{status}")
        pedro = _user(db, klass, f"pedro_{status}")
        _sub(db, ana, t, DUE, team=[pedro], status=status)
        assert _counting_entrega(db, pedro.id, t.id) is None
        assert _counting_entrega(db, ana.id, t.id) is None


def test_a_member_reads_the_authors_review(db, teacher, klass):
    ana, pedro, _ = _team(db, klass)
    t = _item(db, teacher, klass)
    e = _sub(db, ana, t, DUE, team=[pedro])
    db.add(Review(item_post_id=t.id, student_id=ana.id, entrega_post_id=e.id,
                  score=Decimal("80")))
    db.commit()
    review = counting_review(db, t.id, pedro.id, e)
    assert review is not None and review.student_id == ana.id
    assert db.query(Review).filter(Review.student_id == pedro.id).count() == 0


def test_lateness_is_shared(db, teacher, klass):
    ana, pedro, _ = _team(db, klass)
    t = _item(db, teacher, klass)
    _sub(db, ana, t, DUE + timedelta(hours=3), team=[pedro])   # < 24 h late → 90
    a = tareas_rubro(db, ana.id, klass, AFTER)
    p = tareas_rubro(db, pedro.id, klass, AFTER)
    assert a.points == p.points == Decimal("0.9") * klass.tareas_weight


def test_examen_team_by_reply_with_files(db, teacher, klass):
    ana, pedro, _ = _team(db, klass)
    x = _item(db, teacher, klass, "examen")
    sub = _sub(db, ana, x, DUE, team=[pedro], is_entrega=False, files=["r.pdf"])
    assert examen_submission(db, pedro.id, x).id == sub.id
    assert _counting_entrega(db, pedro.id, x.id) is None   # not an entrega


def test_paper_examen_is_individual(db, teacher, klass):
    ana, _, _ = _team(db, klass)
    x = _item(db, teacher, klass, "examen")
    assert examen_submission(db, ana.id, x) is None
    db.add(Review(item_post_id=x.id, student_id=ana.id, score=Decimal("9")))
    db.commit()
    assert counting_review(db, x.id, ana.id, None).score == Decimal("9")


def test_team_of_sees_members_and_authors(db, teacher, klass):
    ana, pedro, luis = _team(db, klass)
    t = _item(db, teacher, klass)
    e = _sub(db, ana, t, DUE, team=[pedro])
    assert team_of(db, pedro.id, t).id == e.id      # as member
    assert team_of(db, ana.id, t).id == e.id        # as author of a team
    assert team_of(db, luis.id, t) is None
    assert team_of(db, pedro.id, t, ignore_author=ana.id) is None   # Ana re-tagging


def test_a_solo_author_is_not_on_a_team(db, teacher, klass):
    ana, _, _ = _team(db, klass)
    t = _item(db, teacher, klass)
    _sub(db, ana, t, DUE)
    assert team_of(db, ana.id, t) is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_teams_engine.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.submissions'`.

- [ ] **Step 3: Write `submissions.py`**

```python
# backend/app/services/submissions.py
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
```

- [ ] **Step 4: Rewire `grades.py`**

In `backend/app/services/grades.py`:

1. Add the import: `from app.services.submissions import counting_entrega, counting_submission`.
2. Replace the bodies of `_counting_entrega` and `examen_submission` (keep names and signatures — 17 callers import them):

```python
def _counting_entrega(db: Session, user_id: int, tarea_id: int) -> Optional[Post]:
    """The entrega that counts for this student — their own or their team's
    (services/submissions.py)."""
    return counting_entrega(db, user_id, tarea_id)


def examen_submission(db: Session, student_id: int, examen: Post) -> Optional[Post]:
    """What counts as this student's examen work, own or team
    (services/submissions.py)."""
    return counting_submission(db, student_id, examen)
```

3. In `counting_review`, read the submission author's review:

```python
def counting_review(db: Session, item_post_id: int, student_id: int,
                    entrega: Optional[Post]) -> Optional[Review]:
    """The review for this student's counting submission, unless it is stale.

    The review lives on the submission's author: a team member's grade *is*
    the author's review of the team entrega (spec 2026-10-28 §2) — never a
    copy. A review is stale when written against a submission since replaced;
    a paper examen has no submission and never goes stale.
    """
    owner = entrega.author_id if entrega is not None else student_id
    review = (
        db.query(Review)
        .filter(Review.item_post_id == item_post_id,
                Review.student_id == owner)
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

4. In `examenes_rubro`, read the review through the examen submission so a team member gets the team's score (keep `count_entregadas` on marked entregas, as before):

```python
    for examen in graded:
        entrega = _counting_entrega(db, user_id, examen.id)
        if entrega is not None:
            entregadas += 1
        submission = examen_submission(db, user_id, examen)
        review = counting_review(db, examen.id, user_id, submission)
```

- [ ] **Step 5: Run the new tests and the whole suite**

Run: `cd backend && python -m pytest tests/test_teams_engine.py -q && python -m pytest -q`
Expected: all PASS. A solo student's results are unchanged (own ∪ ∅ = own; owner = themselves).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/submissions.py backend/app/services/grades.py backend/tests/test_teams_engine.py
git commit -m "feat(grading): team submissions count for every member"
```

---

### Task 4: Publish records mentions and decides the team

**Files:**
- Modify: `backend/app/services/mentions.py` (add `TeamVerdict`, `evaluate_team`, `record_mentions`)
- Modify: `backend/app/schemas.py` (`MentionOut`, `PostOut.mentions`)
- Modify: `backend/app/routers/posts.py` (`create_post`, `serialize_post`)
- Test: `backend/tests/test_mentions_publish.py`

**Interfaces:**
- Consumes: `parse_usernames` (Task 2); `team_of`, `PostMention` (Tasks 1, 3).
- Produces:
  - `MAX_TEAM = 2`
  - `TeamVerdict(username: str, user: Optional[User], reason: Optional[str], team_author: Optional[User] = None)` — `reason` is `None` (ok) or one of `"unknown" | "self" | "author_inactive" | "not_in_class" | "on_team" | "max_team"`.
  - `evaluate_team(db, author: User, item: Post, usernames: List[str]) -> List[TeamVerdict]`
  - `record_mentions(db, post: Post, author: User, item: Optional[Post]) -> None` — `item` is the tarea/examen when `post` is a submission, else `None`.
  - `PostOut.mentions: List[MentionOut]`, `MentionOut{user: AuthorOut, kind: str, removed: bool}`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_mentions_publish.py
"""Publishing parses @mentions; a submission's eligible mentions form the team."""
from datetime import datetime, timezone

import pytest

from app import storage
from app.auth.sessions import create_session
from app.models import Enrollment, Post, PostMention, Review, User

DUE = datetime(2030, 8, 9, 23, 59, tzinfo=timezone.utc)


@pytest.fixture()
def r2_on(monkeypatch):
    monkeypatch.setattr(storage, "is_r2_configured", lambda: True)
    monkeypatch.setattr(storage, "upload_bytes", lambda data, key, content_type: None)
    monkeypatch.setattr(storage, "generate_presigned_url",
                        lambda key, expires=3600: f"https://r2.test/{key}")


def _user(db, klass, handle, status="active"):
    u = User(google_id=f"g-{handle}", email=f"{handle}@example.com",
             name=handle.title(), username=handle)
    db.add(u)
    db.flush()
    if klass is not None:
        db.add(Enrollment(user_id=u.id, class_id=klass.id, status=status))
    db.commit()
    return u


def _h(db, u):
    return {"Authorization": f"Bearer {create_session(db, u)}"}


def _tarea(db, teacher, klass):
    t = Post(author_id=teacher.id, class_id=klass.id, type="tarea", content="T", due_date=DUE)
    db.add(t)
    db.commit()
    return t


def _post(client, db, author, content, **data):
    r = client.post("/api/posts", data={"content": content, **data}, headers=_h(db, author))
    assert r.status_code == 201, r.text
    return r.json()


def _kinds(body):
    return {m["user"]["username"]: m["kind"] for m in body["mentions"]}


def test_a_regular_post_stores_social_mentions(client, db, klass):
    ana = _user(db, klass, "ana")
    _user(db, None, "exalumno")       # in no class: social still works
    body = _post(client, db, ana, "hola @Exalumno y @nadie_existe")
    assert _kinds(body) == {"exalumno": "social"}


def test_an_entrega_makes_a_team_of_two_at_most(client, db, teacher, klass):
    ana, pedro, luis, eva = (_user(db, klass, n) for n in ("ana", "pedro", "luis", "eva"))
    t = _tarea(db, teacher, klass)
    body = _post(client, db, ana, "listo @pedro @luis @eva @ana",
                 parent_id=str(t.id), is_entrega="true")
    assert _kinds(body) == {"pedro": "team", "luis": "team", "eva": "social"}


def test_only_active_classmates_join(client, db, teacher, klass):
    ana = _user(db, klass, "ana")
    _user(db, klass, "fantasma", status="ghost")
    _user(db, None, "otra_clase")
    t = _tarea(db, teacher, klass)
    body = _post(client, db, ana, "@fantasma @otra_clase",
                 parent_id=str(t.id), is_entrega="true")
    assert _kinds(body) == {"fantasma": "social", "otra_clase": "social"}


def test_first_team_wins(client, db, teacher, klass):
    ana, pedro, luis = (_user(db, klass, n) for n in ("ana", "pedro", "luis"))
    t = _tarea(db, teacher, klass)
    _post(client, db, ana, "@pedro", parent_id=str(t.id), is_entrega="true")
    body = _post(client, db, luis, "@pedro", parent_id=str(t.id), is_entrega="true")
    assert _kinds(body) == {"pedro": "social"}
    # …but Ana re-tagging her own team carries it over
    body = _post(client, db, ana, "v2 @pedro", parent_id=str(t.id), is_entrega="true")
    assert _kinds(body) == {"pedro": "team"}


def test_a_question_under_a_tarea_is_only_social(client, db, teacher, klass):
    ana, pedro = _user(db, klass, "ana"), _user(db, klass, "pedro")
    t = _tarea(db, teacher, klass)
    body = _post(client, db, ana, "¿@pedro ya entregaste?", parent_id=str(t.id))
    assert _kinds(body) == {"pedro": "social"}


def test_an_examen_reply_with_files_is_a_submission(client, db, teacher, klass, r2_on):
    ana, pedro = _user(db, klass, "ana"), _user(db, klass, "pedro")
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen", content="P1",
             examen_mode="digital")
    db.add(x)
    db.commit()
    r = client.post("/api/posts",
                    data={"content": "@pedro", "parent_id": str(x.id)},
                    files=[("files", ("r.pdf", b"x" * 10, "application/pdf"))],
                    headers=_h(db, ana))
    assert r.status_code == 201, r.text
    assert _kinds(r.json()) == {"pedro": "team"}


def test_an_inactive_author_forms_no_team(client, db, teacher, klass, r2_on):
    polizon = _user(db, klass, "polizon", status="polizon")
    _user(db, klass, "pedro")
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen", content="P1",
             examen_mode="digital")
    db.add(x)
    db.commit()
    r = client.post("/api/posts", data={"content": "@pedro", "parent_id": str(x.id)},
                    files=[("files", ("r.pdf", b"x" * 10, "application/pdf"))],
                    headers=_h(db, polizon))
    assert r.status_code == 201, r.text
    assert _kinds(r.json()) == {"pedro": "social"}


def test_a_member_sees_the_teams_score_in_the_thread(client, db, teacher, teacher_headers, klass):
    ana, pedro, luis = (_user(db, klass, n) for n in ("ana", "pedro", "luis"))
    t = _tarea(db, teacher, klass)
    e = _post(client, db, ana, "@pedro", parent_id=str(t.id), is_entrega="true")
    db.add(Review(item_post_id=t.id, student_id=ana.id, entrega_post_id=e["id"], score=90))
    db.commit()
    def reply(u):
        replies = client.get(f"/api/posts/{t.id}", headers=_h(db, u)).json()["replies"]
        return next(r for r in replies if r["id"] == e["id"])
    assert float(reply(pedro)["my_review"]["score"]) == 90.0
    assert reply(luis)["my_review"] is None


def test_a_deleted_post_keeps_its_mention_rows(client, db, klass):
    ana, pedro = _user(db, klass, "ana"), _user(db, klass, "pedro")
    body = _post(client, db, ana, "hola @pedro")
    client.delete(f"/api/posts/{body['id']}", headers=_h(db, ana))
    # the row stays (never deleted); serialization hides it with the text
    assert db.query(PostMention).filter(PostMention.post_id == body["id"]).count() == 1
```

(`test_a_deleted_post_keeps_its_mention_rows` only asserts the row survives — a deleted post with no replies 404s on GET. The serializer's `[] if removed` mirrors how it already blanks `content` and `attachments`.)

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_mentions_publish.py -q`
Expected: FAIL — `KeyError: 'mentions'`.

- [ ] **Step 3: Add team evaluation to `mentions.py`**

Append to `backend/app/services/mentions.py` (and extend its imports):

```python
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Enrollment, Post, PostMention, User
from app.services.submissions import team_of

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
    Decided once — never recomputed (first team wins must not flip later)."""
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
```

- [ ] **Step 4: Schema and serializer**

In `backend/app/schemas.py`, before `PostOut`:

```python
class MentionOut(BaseModel):
    user: AuthorOut
    kind: str            # social|team
    removed: bool = False
```

In `PostOut`, after `is_submission`: `mentions: List[MentionOut] = []` (ensure `List` is imported).

In `backend/app/routers/posts.py` `serialize_post`:

```python
    removed = post.status == "deleted"
    # A team member reads the team entrega's score like the author does.
    member = viewer is not None and any(
        m.user_id == viewer.id and m.kind == "team" and m.removed_at is None
        for m in post.mentions)
    private = viewer is not None and (
        viewer.id == post.author_id or viewer.role == "teacher" or member)
```

and add to the `PostOut(...)` call:

```python
        mentions=[] if removed else [
            MentionOut(user=AuthorOut.model_validate(m.user), kind=m.kind,
                       removed=m.removed_at is not None)
            for m in post.mentions],
```

(import `MentionOut` from `app.schemas`). In `get_thread`, the review lookup is keyed by `Review.entrega_post_id`, so a team entrega's review (the author's) already lands on it — no change there.

- [ ] **Step 5: Call it from `create_post`**

In `create_post`, right after `db.flush()` (post has an id) and before attachments:

```python
    # A submission: an entrega, or a reply with files straight under an
    # examen (the examen_submission rule). Only then can mentions form a team.
    submission_item = parent if parent is not None and (
        entrega or (parent.type == "examen" and file_payloads)) else None
    record_mentions(db, post, user, submission_item)
```

(import `record_mentions` from `app.services.mentions`). The final reload already re-queries the post, and `mentions` loads via selectin.

- [ ] **Step 6: Run tests**

Run: `cd backend && python -m pytest tests/test_mentions_publish.py -q && python -m pytest -q`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/mentions.py backend/app/schemas.py backend/app/routers/posts.py backend/tests/test_mentions_publish.py
git commit -m "feat(mentions): store mentions on publish; a submission's form the team"
```

---

### Task 5: `users/search` and `team-check`

**Files:**
- Modify: `backend/app/routers/users.py` (`GET /api/users/search`)
- Modify: `backend/app/routers/posts.py` (`GET /api/posts/{item_id}/team-check`)
- Test: `backend/tests/test_mentions_api.py`

**Interfaces:**
- Consumes: `evaluate_team`, `parse_usernames` (Task 4/2); `viewer_class_ids` (`app.services.visibility`).
- Produces:
  - `GET /api/users/search?q=` → `{"users": [AuthorOut]}` (≤ 8, classmates first, never the viewer).
  - `GET /api/posts/{item_id}/team-check?u=a&u=b` → `{"results": [{"username": str, "status": "ok" | reason, "team_author": str | null}]}`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_mentions_api.py
from datetime import datetime, timezone

from app.auth.sessions import create_session
from app.models import Class, Enrollment, Post, PostMention, User
from datetime import date

DUE = datetime(2030, 8, 9, 23, 59, tzinfo=timezone.utc)


def _user(db, klass, handle, name=None, status="active"):
    u = User(google_id=f"g-{handle}", email=f"{handle}@example.com",
             name=name or handle.title(), username=handle)
    db.add(u)
    db.flush()
    if klass is not None:
        db.add(Enrollment(user_id=u.id, class_id=klass.id, status=status))
    db.commit()
    return u


def _h(db, u):
    return {"Authorization": f"Bearer {create_session(db, u)}"}


def _search(client, db, viewer, q):
    r = client.get("/api/users/search", params={"q": q}, headers=_h(db, viewer))
    assert r.status_code == 200, r.text
    return [u["username"] for u in r.json()["users"]]


def test_search_puts_classmates_first_and_never_the_viewer(client, db, klass):
    me = _user(db, klass, "ana")
    _user(db, None, "andres")             # not a classmate
    _user(db, klass, "anahi")
    assert _search(client, db, me, "an") == ["anahi", "andres"]


def test_search_matches_name_prefix_and_strips_the_at(client, db, klass):
    me = _user(db, klass, "ana")
    _user(db, klass, "pl", name="Pedro López")
    assert _search(client, db, me, "@ped") == ["pl"]


def test_search_treats_underscore_literally(client, db, klass):
    me = _user(db, klass, "ana")
    _user(db, klass, "a_b")
    _user(db, klass, "axb")
    assert _search(client, db, me, "a_") == ["a_b"]


def test_search_caps_at_eight(client, db, klass):
    me = _user(db, klass, "zz_me")
    for i in range(10):
        _user(db, klass, f"bea{i}")
    assert len(_search(client, db, me, "bea")) == 8


def test_team_check_reports_each_reason(client, db, teacher, klass):
    ana, pedro, luis, eva = (_user(db, klass, n) for n in ("ana", "pedro", "luis", "eva"))
    _user(db, None, "fuera")
    t = Post(author_id=teacher.id, class_id=klass.id, type="tarea", content="T", due_date=DUE)
    db.add(t)
    db.flush()
    other = Post(author_id=luis.id, class_id=klass.id, parent_id=t.id, content="@eva",
                 is_entrega=True)
    db.add(other)
    db.flush()
    db.add(PostMention(post_id=other.id, user_id=eva.id, kind="team"))
    db.commit()
    r = client.get(f"/api/posts/{t.id}/team-check",
                   params=[("u", "Pedro"), ("u", "eva"), ("u", "fuera"), ("u", "ana"),
                           ("u", "nadie_aqui")],
                   headers=_h(db, ana))
    assert r.status_code == 200, r.text
    assert r.json()["results"] == [
        {"username": "pedro", "status": "ok", "team_author": None},
        {"username": "eva", "status": "on_team", "team_author": "luis"},
        {"username": "fuera", "status": "not_in_class", "team_author": None},
        {"username": "ana", "status": "self", "team_author": None},
        {"username": "nadie_aqui", "status": "unknown", "team_author": None},
    ]


def test_team_check_needs_a_tarea_or_examen(client, db, klass):
    ana = _user(db, klass, "ana")
    p = Post(author_id=ana.id, class_id=klass.id, content="hola")
    db.add(p)
    db.commit()
    r = client.get(f"/api/posts/{p.id}/team-check", params={"u": "x_y"}, headers=_h(db, ana))
    assert r.status_code == 422
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_mentions_api.py -q`
Expected: FAIL — 404/405 on both routes.

- [ ] **Step 3: Implement `users/search`**

In `backend/app/routers/users.py` (imports: `Query` from fastapi, `func, or_` from sqlalchemy, `AuthorOut` from schemas, `viewer_class_ids` from `app.services.visibility`). The users router is included before profiles, so `/search` wins over `/{username}`:

```python
SEARCH_LIMIT = 8


def _like_prefix(term: str) -> str:
    # `_` and `%` are SQL wildcards; usernames contain `_`.
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@router.get("/search")
def search_users(q: str = Query(..., min_length=1, max_length=40),
                 user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """@mention autocomplete: anyone with a username (the feed is global),
    the viewer's classmates and teachers first."""
    term = q.strip().lstrip("@").lower()
    if not term:
        return {"users": []}
    like = _like_prefix(term)
    rows = (db.query(User)
            .filter(User.username.isnot(None), User.id != user.id,
                    or_(User.username.like(like, escape="\\"),
                        func.lower(User.name).like(like, escape="\\")))
            .order_by(User.username)
            .limit(50).all())
    mine = viewer_class_ids(db, user)
    close = {uid for (uid,) in db.query(Enrollment.user_id).filter(
        Enrollment.class_id.in_(mine), Enrollment.status == "active")} if mine else set()
    close |= {tid for (tid,) in db.query(Class.teacher_id).filter(Class.id.in_(mine))} if mine else set()
    rows.sort(key=lambda u: (u.id not in close, u.username))
    return {"users": [AuthorOut.model_validate(u) for u in rows[:SEARCH_LIMIT]]}
```

- [ ] **Step 4: Implement `team-check`**

In `backend/app/routers/posts.py` (import `evaluate_team` from `app.services.mentions`; `List`, `Query` already imported):

```python
@router.get("/{item_id}/team-check")
def team_check(item_id: int, u: List[str] = Query(default=[]),
               user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """What publish would decide for these @mentions, read-only — so the
    composer can warn before the entrega is sent (it never blocks)."""
    item = db.get(Post, item_id)
    if item is None or item.status != "active":
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if item.type not in ("tarea", "examen"):
        raise HTTPException(status_code=422, detail="Sólo una tarea o un examen tiene equipo")
    names: List[str] = []
    for raw in u:
        n = raw.strip().lstrip("@").lower()
        if n and n not in names:
            names.append(n)
    return {"results": [
        {"username": v.username,
         "status": "ok" if v.reason is None else v.reason,
         "team_author": v.team_author.username if v.team_author else None}
        for v in evaluate_team(db, user, item, names[:10])]}
```

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_mentions_api.py -q && python -m pytest -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/users.py backend/app/routers/posts.py backend/tests/test_mentions_api.py
git commit -m "feat(mentions): user search and team-check endpoints"
```

---

### Task 6: Teacher removes / restores a team member

**Files:**
- Modify: `backend/app/routers/posts.py`
- Test: `backend/tests/test_team_remove.py`

**Interfaces:**
- Consumes: `team_of` (Task 3), `_teacher_item` (existing in posts.py), `serialize_post`.
- Produces: `POST /api/posts/{post_id}/team/{user_id}/remove` and `POST /api/posts/{post_id}/team/{user_id}/restore` → `PostOut` of the submission (with updated `mentions`). 403 for non-owners, 404 if that user is not a team mention, 409 on restore when they're on another team now.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_team_remove.py
from datetime import datetime, timezone

from app.auth.sessions import create_session
from app.models import Enrollment, Post, PostMention, User
from app.services.grades import _counting_entrega

DUE = datetime(2030, 8, 9, 23, 59, tzinfo=timezone.utc)


def _user(db, klass, handle):
    u = User(google_id=f"g-{handle}", email=f"{handle}@example.com",
             name=handle.title(), username=handle)
    db.add(u)
    db.flush()
    db.add(Enrollment(user_id=u.id, class_id=klass.id))
    db.commit()
    return u


def _setup(db, teacher, klass):
    ana, pedro, luis = (_user(db, klass, n) for n in ("ana", "pedro", "luis"))
    t = Post(author_id=teacher.id, class_id=klass.id, type="tarea", content="T", due_date=DUE)
    db.add(t)
    db.flush()
    e = Post(author_id=ana.id, class_id=klass.id, parent_id=t.id, content="@pedro",
             is_entrega=True, created_at=DUE)
    db.add(e)
    db.flush()
    db.add(PostMention(post_id=e.id, user_id=pedro.id, kind="team"))
    db.commit()
    return ana, pedro, luis, t, e


def test_remove_then_restore(client, db, teacher, teacher_headers, klass):
    ana, pedro, _, t, e = _setup(db, teacher, klass)
    r = client.post(f"/api/posts/{e.id}/team/{pedro.id}/remove", headers=teacher_headers)
    assert r.status_code == 200, r.text
    assert r.json()["mentions"][0]["removed"] is True
    assert _counting_entrega(db, pedro.id, t.id) is None
    m = db.query(PostMention).one()
    assert m.removed_by == teacher.id
    r = client.post(f"/api/posts/{e.id}/team/{pedro.id}/restore", headers=teacher_headers)
    assert r.status_code == 200, r.text
    assert r.json()["mentions"][0]["removed"] is False
    assert _counting_entrega(db, pedro.id, t.id).id == e.id


def test_restore_refused_when_on_another_team(client, db, teacher, teacher_headers, klass):
    ana, pedro, luis, t, e = _setup(db, teacher, klass)
    client.post(f"/api/posts/{e.id}/team/{pedro.id}/remove", headers=teacher_headers)
    other = Post(author_id=luis.id, class_id=klass.id, parent_id=t.id, content="@pedro",
                 is_entrega=True, created_at=DUE)
    db.add(other)
    db.flush()
    db.add(PostMention(post_id=other.id, user_id=pedro.id, kind="team"))
    db.commit()
    r = client.post(f"/api/posts/{e.id}/team/{pedro.id}/restore", headers=teacher_headers)
    assert r.status_code == 409
    assert "@luis" in r.json()["detail"]


def test_only_the_teacher_and_only_team_mentions(client, db, teacher, teacher_headers, klass):
    ana, pedro, luis, t, e = _setup(db, teacher, klass)
    h = {"Authorization": f"Bearer {create_session(db, ana)}"}
    assert client.post(f"/api/posts/{e.id}/team/{pedro.id}/remove", headers=h).status_code == 403
    assert client.post(f"/api/posts/{e.id}/team/{luis.id}/remove",
                       headers=teacher_headers).status_code == 404
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_team_remove.py -q`
Expected: FAIL — 404/405.

- [ ] **Step 3: Implement**

In `backend/app/routers/posts.py` (import `team_of` from `app.services.submissions`, `PostMention` from models):

```python
def _team_mention(db: Session, post_id: int, user_id: int, user: User):
    post = db.get(Post, post_id)
    if post is None or post.parent_id is None:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    item = _teacher_item(db, post.parent_id, user)
    m = (db.query(PostMention)
         .filter(PostMention.post_id == post.id, PostMention.user_id == user_id,
                 PostMention.kind == "team").first())
    if m is None:
        raise HTTPException(status_code=404, detail="Esa persona no está en el equipo")
    return post, item, m


def _team_response(db: Session, post: Post, user: User) -> PostOut:
    db.refresh(post)
    return serialize_post(post, liked_ids=set(), viewer=user)


@router.post("/{post_id}/team/{user_id}/remove", response_model=PostOut)
def remove_from_team(post_id: int, user_id: int, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """A member who didn't work stops receiving this grade — a flag, never a
    delete and never a different number (one grade per entrega)."""
    post, _item, m = _team_mention(db, post_id, user_id, user)
    if m.removed_at is None:
        m.removed_at = utcnow()
        m.removed_by = user.id
        db.commit()
    return _team_response(db, post, user)


@router.post("/{post_id}/team/{user_id}/restore", response_model=PostOut)
def restore_to_team(post_id: int, user_id: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    post, item, m = _team_mention(db, post_id, user_id, user)
    if m.removed_at is not None:
        other = team_of(db, user_id, item)
        if other is not None:
            raise HTTPException(
                status_code=409,
                detail=f"@{m.user.username} ya está en el equipo de @{other.author.username}")
        m.removed_at = None
        m.removed_by = None
        db.commit()
    return _team_response(db, post, user)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_team_remove.py -q && python -m pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/posts.py backend/tests/test_team_remove.py
git commit -m "feat(teams): teacher removes or restores a team member"
```

---

### Task 7: Teacher surfaces follow the team — `/revisar`, reviews, pending, thread

**Files:**
- Modify: `backend/app/routers/review_queue.py` (`entregas_queue`, `examen_roster`)
- Modify: `backend/app/routers/reviews.py` (`upsert_review`, `accept_suggested`)
- Modify: `backend/app/services/feed_query.py` (`teacher_pending`)
- Modify: `backend/app/routers/posts.py` (`_examen_submissions`, `get_thread`)
- Test: `backend/tests/test_teams_teacher.py`

**Interfaces:**
- Consumes: `_counting_entrega`, `examen_submission`, `counting_review` (Task 3); `live_team_member_ids` (Task 3).
- Produces:
  - `/api/review/entregas` rows gain `team: [{"user": QueueStudent, "removed": bool}]`; `student` is the submission **author**; one row per submission; `pending` counts submissions.
  - `/api/review/examenes/{id}` rows gain `team_of: QueueStudent | null`; `score` is the counting review's.
  - `PUT /api/reviews` for a team member writes the author's review.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_teams_teacher.py
"""Teacher surfaces agree with the engine on team submissions (spec §2–§3)."""
from datetime import datetime, timedelta, timezone

from datetime import date

from app.models import Enrollment, Post, PostMention, Review, User, utcnow
from app.services.feed_query import teacher_pending
from app.services.grades import _counting_entrega

# Fixed past dates for posts, real "now" for pending: reviews saved through the
# API get updated_at = utcnow(), and teacher_pending only counts what happened
# at or before as_of. The class is kept running so the test doesn't expire.
DUE = datetime(2026, 8, 9, 23, 59, tzinfo=timezone.utc)
NOW = utcnow() + timedelta(days=1)


def _running(db, klass):
    klass.end_date = date(2099, 1, 1)
    db.commit()


def _user(db, klass, handle, status="active"):
    u = User(google_id=f"g-{handle}", email=f"{handle}@example.com",
             name=handle.title(), username=handle)
    db.add(u)
    db.flush()
    db.add(Enrollment(user_id=u.id, class_id=klass.id, status=status))
    db.commit()
    return u


def _sub(db, author, item, team=(), is_entrega=True, at=DUE):
    p = Post(author_id=author.id, class_id=item.class_id, parent_id=item.id,
             content="x", is_entrega=is_entrega, created_at=at)
    db.add(p)
    db.flush()
    for u in team:
        db.add(PostMention(post_id=p.id, user_id=u.id, kind="team"))
    db.commit()
    return p


def _tarea(db, teacher, klass):
    t = Post(author_id=teacher.id, class_id=klass.id, type="tarea", content="T",
             due_date=DUE, created_at=DUE - timedelta(days=3))
    db.add(t)
    db.commit()
    return t


def test_entregas_queue_has_one_row_per_team(client, db, teacher, teacher_headers, klass):
    ana, pedro, luis, eva = (_user(db, klass, n) for n in ("ana", "pedro", "luis", "eva"))
    t = _tarea(db, teacher, klass)
    e = _sub(db, ana, t, team=[pedro, luis])
    _sub(db, eva, t)
    g = client.get(f"/api/review/entregas?class_id={klass.id}",
                   headers=teacher_headers).json()["groups"][0]
    assert g["pending"] == 2
    row = next(r for r in g["entregas"] if r["entrega_post_id"] == e.id)
    assert row["student"]["username"] == "ana"
    assert [(m["user"]["username"], m["removed"]) for m in row["team"]] == [
        ("pedro", False), ("luis", False)]


def test_grading_a_member_writes_the_authors_review(client, db, teacher, teacher_headers, klass):
    ana, pedro = _user(db, klass, "ana"), _user(db, klass, "pedro")
    t = _tarea(db, teacher, klass)
    e = _sub(db, ana, t, team=[pedro])
    r = client.put("/api/reviews", json={"item_post_id": t.id, "student_id": pedro.id,
                                         "entrega_post_id": e.id, "score": 85},
                   headers=teacher_headers)
    assert r.status_code == 200, r.text
    assert [rv.student_id for rv in db.query(Review).all()] == [ana.id]


def test_grading_someone_with_an_entrega_that_isnt_theirs_is_rejected(
        client, db, teacher, teacher_headers, klass):
    ana, eva = _user(db, klass, "ana"), _user(db, klass, "eva")
    t = _tarea(db, teacher, klass)
    e = _sub(db, ana, t)
    r = client.put("/api/reviews", json={"item_post_id": t.id, "student_id": eva.id,
                                         "entrega_post_id": e.id, "score": 85},
                   headers=teacher_headers)
    assert r.status_code == 422


def test_pending_counts_one_per_team_and_agrees_with_the_engine(db, teacher, klass):
    _running(db, klass)
    ana, pedro, luis, eva = (_user(db, klass, n) for n in ("ana", "pedro", "luis", "eva"))
    t = _tarea(db, teacher, klass)
    _sub(db, pedro, t, at=DUE - timedelta(hours=5))          # replaced by the team's
    e = _sub(db, ana, t, team=[pedro, luis])
    _sub(db, eva, t)
    assert teacher_pending(db, teacher.id, NOW)[t.id][1] == 2
    engine = {_counting_entrega(db, u.id, t.id).id for u in (ana, pedro, luis, eva)}
    assert len(engine) == 2 and e.id in engine
    db.add(Review(item_post_id=t.id, student_id=ana.id, entrega_post_id=e.id, score=80,
                  created_at=DUE, updated_at=DUE))
    db.commit()
    assert teacher_pending(db, teacher.id, NOW)[t.id][1] == 1


def test_a_ghost_author_still_counts_for_active_members(client, db, teacher, teacher_headers, klass):
    _running(db, klass)
    ana, pedro = _user(db, klass, "ana"), _user(db, klass, "pedro")
    t = _tarea(db, teacher, klass)
    e = _sub(db, ana, t, team=[pedro])
    db.query(Enrollment).filter(Enrollment.user_id == ana.id).update({"status": "ghost"})
    db.commit()
    assert teacher_pending(db, teacher.id, NOW)[t.id][1] == 1
    r = client.put("/api/reviews", json={"item_post_id": t.id, "student_id": pedro.id,
                                         "entrega_post_id": e.id, "score": 70},
                   headers=teacher_headers)
    assert r.status_code == 200, r.text
    assert t.id not in teacher_pending(db, teacher.id, NOW)


def test_examen_roster_shows_the_team_and_the_shared_score(client, db, teacher, teacher_headers, klass):
    ana, pedro = _user(db, klass, "ana"), _user(db, klass, "pedro")
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen", content="P",
             examen_mode="digital")
    db.add(x)
    db.commit()
    sub = _sub(db, ana, x, team=[pedro])           # marked entrega
    client.put("/api/reviews", json={"item_post_id": x.id, "student_id": pedro.id,
                                     "score": 9}, headers=teacher_headers)
    rows = {r["student"]["username"]: r for r in client.get(
        f"/api/review/examenes/{x.id}", headers=teacher_headers).json()["rows"]}
    assert rows["pedro"]["team_of"]["username"] == "ana"
    assert rows["ana"]["team_of"] is None
    assert rows["pedro"]["score"] == rows["ana"]["score"] == 9.0
    assert rows["pedro"]["submission"]["post_id"] == sub.id


def test_the_thread_marks_a_team_examen_submission_once(client, db, teacher, teacher_headers, klass):
    ana, pedro = _user(db, klass, "ana"), _user(db, klass, "pedro")
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen", content="P",
             examen_mode="digital")
    db.add(x)
    db.commit()
    sub = _sub(db, ana, x, team=[pedro])
    client.put("/api/reviews", json={"item_post_id": x.id, "student_id": ana.id,
                                     "score": 8}, headers=teacher_headers)
    replies = {r["id"]: r for r in client.get(
        f"/api/posts/{x.id}", headers=teacher_headers).json()["replies"]}
    assert replies[sub.id]["is_submission"] is True
    assert float(replies[sub.id]["my_review"]["score"]) == 8.0


def test_accept_suggested_grades_a_team_entrega_once(client, db, teacher, teacher_headers, klass):
    ana, pedro = _user(db, klass, "ana"), _user(db, klass, "pedro")
    t = _tarea(db, teacher, klass)
    e = _sub(db, ana, t, team=[pedro])
    r = client.post("/api/reviews/accept-suggested",
                    json={"item_post_id": t.id, "entrega_post_ids": [e.id]},
                    headers=teacher_headers)
    assert r.json() == {"graded": 1}
    assert db.query(Review).count() == 1
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_teams_teacher.py -q`
Expected: several FAIL (no `team`, pending counts 3, member review written to Pedro, etc.).

- [ ] **Step 3: `entregas_queue` — one row per submission**

In `backend/app/routers/review_queue.py`, add:

```python
def _team_json(post: Post) -> list:
    return [{"user": _student_json(m.user), "removed": m.removed_at is not None}
            for m in post.mentions if m.kind == "team"]
```

Replace the per-tarea loop body in `entregas_queue`:

```python
    for tarea in tareas:
        # One row per submission: a team entrega counts for up to three
        # students but is graded once, as its author's review.
        by_sub = {}
        for student in _active_students(db, klass.id):
            entrega = _counting_entrega(db, student.id, tarea.id)
            if entrega is not None:
                by_sub.setdefault(entrega.id, entrega)
        entregas = []
        for entrega in sorted(by_sub.values(),
                              key=lambda p: (p.author.username or "", p.id)):
            review = counting_review(db, tarea.id, entrega.author_id, entrega)
            reviewed = review is not None
            if status == "unopened" and reviewed:
                continue
            auto = (lateness_score(entrega.created_at, tarea.due_date)
                    if tarea.due_date is not None else None)
            entregas.append({
                "student": _student_json(entrega.author),
                "team": _team_json(entrega),
                "entrega_post_id": entrega.id,
                "created_at": entrega.created_at,
                "auto_score": float(auto) if auto is not None else None,
                "reviewed": reviewed,
                "score": float(review.score) if reviewed and review.score is not None else None,
            })
```

(keep the existing `if not entregas: continue` / `groups.append(...)` that follows).

- [ ] **Step 4: `examen_roster` — team_of and the counting review**

Replace the row loop:

```python
    for student in _active_students(db, examen.class_id):
        entrega = _counting_entrega(db, student.id, examen.id)
        submission = examen_submission(db, student.id, examen)
        review = counting_review(db, examen.id, student.id, submission)
        team_of = (_student_json(submission.author)
                   if submission is not None and submission.author_id != student.id else None)
        rows.append({
            "student": _student_json(student),
            "entrega_post_id": entrega.id if entrega else None,
            "submission": _submission_json(submission),
            "team_of": team_of,
            "score": float(review.score) if review and review.score is not None else None,
        })
```

- [ ] **Step 5: `upsert_review` — resolve the review owner**

In `backend/app/routers/reviews.py` (import `examen_submission` from grades, `live_team_member_ids` from `app.services.submissions`), after the enrollment check replace the entrega/review block:

```python
    # A team member's grade is the author's review of the team submission
    # (spec 2026-10-28): grading any member's row writes that one review.
    counting = (_counting_entrega(db, body.student_id, item.id) if item.type == "tarea"
                else examen_submission(db, body.student_id, item))
    owner = body.student_id
    auto = None
    if body.entrega_post_id is not None:
        entrega = db.get(Post, body.entrega_post_id)
        if entrega is None or entrega.parent_id != item.id:
            raise HTTPException(status_code=422,
                                detail="Esa entrega no pertenece a esta tarea")
        if entrega.author_id != body.student_id and (
                counting is None or counting.id != entrega.id):
            raise HTTPException(status_code=422,
                                detail="Esa entrega no es de ese alumno")
        owner = entrega.author_id
        if item.due_date is not None:
            auto = lateness_score(entrega.created_at, item.due_date)
    elif counting is not None:
        owner = counting.author_id

    review = (
        db.query(Review)
        .filter(Review.item_post_id == item.id, Review.student_id == owner)
        .first()
    )
    if review is None:
        review = Review(item_post_id=item.id, student_id=owner)
        db.add(review)
```

(the rest — assigning `entrega_post_id`, `score`, `auto_score`, … — stays).

- [ ] **Step 6: `accept_suggested` — a team entrega once, even with a ghost author**

Replace `if e.author_id not in active: continue` with:

```python
        counts_for = [e.author_id, *live_team_member_ids(db, e)]
        if not any(uid in active for uid in counts_for):
            continue
```

The rest is unchanged: Ana's own `_counting_entrega` is her team entrega (an author on a team can't be tagged by another), and the review row is hers.

- [ ] **Step 7: `teacher_pending` — inline the team rule**

In `backend/app/services/feed_query.py` (import `PostMention` from models), replace everything from `by_item = defaultdict(list)` to the end of the function:

```python
    reply_ids = [r.id for r in replies]
    team_by_post: Dict[int, List[int]] = defaultdict(list)
    if reply_ids:
        for pid, uid in (db.query(PostMention.post_id, PostMention.user_id)
                         .filter(PostMention.post_id.in_(reply_ids),
                                 PostMention.kind == "team",
                                 or_(PostMention.removed_at.is_(None),
                                     PostMention.removed_at > as_of))):
            team_by_post[pid].append(uid)

    by_item = defaultdict(list)
    for r in replies:
        by_item[r.parent_id].append(r)

    for item in items:
        # Each author's own current submission — every author, active or not:
        # a ghost author's team entrega still counts for active members.
        own_entrega: Dict[int, tuple] = {}
        own_upload: Dict[int, tuple] = {}
        for r in by_item[item.id]:
            at = aware(r.created_at)
            if r.is_entrega and (r.author_id not in own_entrega
                                 or (at, r.id) > own_entrega[r.author_id][::-1]):
                own_entrega[r.author_id] = (r.id, at)
            if r.has_files and (r.author_id not in own_upload
                                or (at, r.id) > own_upload[r.author_id][::-1]):
                own_upload[r.author_id] = (r.id, at)
        own = dict(own_entrega)
        if item.type == "examen":
            for uid, v in own_upload.items():
                own.setdefault(uid, v)
        # Who each submission counts for: its author, plus live team members
        # (a team submission is live while it is its author's own current one —
        # services/submissions.py). Newest wins per student.
        counts: Dict[int, tuple] = {uid: (sid, at, uid) for uid, (sid, at) in own.items()}
        for author, (sid, at) in own.items():
            for member in team_by_post.get(sid, []):
                cur = counts.get(member)
                if cur is None or (at, sid) > (cur[1], cur[0]):
                    counts[member] = (sid, at, author)
        # One pending item per submission that counts for an active student.
        subs: Dict[int, tuple] = {}
        for uid, (sid, at, author) in counts.items():
            if (item.class_id, uid) in active:
                subs[sid] = (at, author)
        ungraded = []
        for sid, (at, author) in subs.items():
            rv = reviews.get((item.id, author))
            done = (rv is not None
                    and aware(rv.updated_at or rv.created_at) <= as_of
                    # counting_review: a review of a replaced entrega is stale.
                    and (rv.entrega_post_id is None or rv.entrega_post_id == sid)
                    and (item.type == "tarea" or rv.score is not None))
            if not done:
                ungraded.append(at)
        if ungraded:
            out[item.id] = (max(ungraded), len(ungraded))
    return out
```

Make sure `List` is imported from `typing` and `or_` from `sqlalchemy` (both likely already are — check the file's imports). The `own_entrega[...][::-1]` turns `(id, at)` into `(at, id)` for the tie-break.

- [ ] **Step 8: Thread — team submissions and their reviews**

In `backend/app/routers/posts.py`, change `_examen_submissions` to return `Dict[int, Post]` (student id → submission post) and include team members of replies as candidates:

```python
def _examen_submissions(db: Session, examen: Post, user: User,
                        replies: List[Post]) -> Dict[int, Post]:
    """student id → the post that holds their examen work, for the teacher who
    grades it; empty for anyone else. Same rule as the /revisar roster."""
    if examen.type != "examen" or user.role != "teacher":
        return {}
    klass = db.get(Class, examen.class_id) if examen.class_id else None
    if klass is None or klass.teacher_id != user.id:
        return {}
    top = [r for r in replies if r.parent_id == examen.id]
    candidates = {r.author_id for r in top} | {
        m.user_id for r in top for m in r.mentions if m.kind == "team"}
    if not candidates:
        return {}
    active = [uid for (uid,) in db.query(Enrollment.user_id).filter(
        Enrollment.class_id == klass.id, Enrollment.status == "active",
        Enrollment.user_id.in_(candidates))]
    out: Dict[int, Post] = {}
    for uid in active:
        sub = examen_submission(db, uid, examen)
        if sub is not None:
            out[uid] = sub
    return out
```

And in `get_thread` replace the `submissions` block:

```python
    submissions = _examen_submissions(db, post, user, replies)
    sub_posts = {s.id: s for s in submissions.values()}
    for sub in sub_posts.values():
        # The review lives on the submission's author, team or not.
        rv = counting_review(db, post.id, sub.author_id, sub)
        if rv is not None:
            review_by_post[sub.id] = rv
```

and pass `submissions=set(sub_posts)` to `serialize_post`. Import `counting_review` from `app.services.grades` and `Dict` from `typing`.

- [ ] **Step 9: Run tests**

Run: `cd backend && python -m pytest tests/test_teams_teacher.py -q && python -m pytest -q`
Expected: all PASS — including the earlier `test_examen_thread.py`, `test_review_queue.py`, `test_accept_suggested.py`, `test_feed_tiers.py` (solo behaviour is unchanged).

- [ ] **Step 10: Commit**

```bash
git add backend/app/routers/review_queue.py backend/app/routers/reviews.py backend/app/services/feed_query.py backend/app/routers/posts.py backend/tests/test_teams_teacher.py
git commit -m "feat(teams): /revisar, reviews, pending and thread grade a team once"
```

---

### Task 8: Frontend mention helpers

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Create: `frontend/src/lib/mentions.ts`, `frontend/src/lib/mentions.test.ts`
- Create: `frontend/src/lib/useDebounced.ts`

**Interfaces:**
- Produces (types): `Mention { user: Author; kind: "social" | "team"; removed: boolean }`; `Post.mentions?: Mention[]`; `TeamMember { user: QueueStudent; removed: boolean }`; `EntregaRow.team: TeamMember[]`; examen roster row `team_of: QueueStudent | null`; `TeamCheckResult { username: string; status: "ok" | "unknown" | "self" | "author_inactive" | "not_in_class" | "on_team" | "max_team"; team_author: string | null }`.
- Produces (functions):
  - `parseUsernames(content: string): string[]` — mirrors the server.
  - `splitMentions(content: string, mentions?: Mention[]): Segment[]`, `Segment = { text: string } | { mention: Author }`
  - `activeMention(value: string, caret: number): { start: number; query: string } | null`
  - `insertMention(value: string, start: number, caret: number, username: string): { value: string; caret: number }`
  - `liveTeam(post: Pick<Post, "mentions">): Author[]`
  - `useDebounced<T>(value: T, ms?: number): T`

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/lib/mentions.test.ts
import { describe, expect, it } from "vitest";
import {
  activeMention,
  insertMention,
  liveTeam,
  parseUsernames,
  splitMentions,
  MENTION_SOURCE,
} from "./mentions";
import type { Author, Mention } from "./types";

const ana: Author = { id: 1, username: "ana", name: "Ana", avatar_url: null, role: "student" };
const m = (user: Author, kind: "social" | "team" = "social", removed = false): Mention => ({
  user, kind, removed,
});

describe("parseUsernames", () => {
  it("mirrors the server: ordered, unique, lowercase", () => {
    expect(parseUsernames("con @Ana y @pedro_2, otra vez @ana")).toEqual(["ana", "pedro_2"]);
  });
  it("ignores emails, short and glued @", () => {
    expect(parseUsernames("pedro@gmail.com @ab a@pedro hola@@x")).toEqual([]);
  });
});

describe("splitMentions", () => {
  it("links only mentions the server resolved", () => {
    expect(splitMentions("hola @Ana y @nadie", [m(ana)])).toEqual([
      { text: "hola " },
      { mention: ana },
      { text: " y @nadie" },
    ]);
  });
  it("is plain text without mentions", () => {
    expect(splitMentions("pedro@gmail.com")).toEqual([{ text: "pedro@gmail.com" }]);
  });
});

describe("activeMention", () => {
  it("finds the @word under the caret", () => {
    expect(activeMention("hola @an", 8)).toEqual({ start: 5, query: "an" });
  });
  it("needs at least one letter, and not inside an email", () => {
    expect(activeMention("hola @", 6)).toBeNull();
    expect(activeMention("pedro@gm", 8)).toBeNull();
  });
});

describe("insertMention", () => {
  it("replaces the partial word and adds a space", () => {
    expect(insertMention("hola @an qué", 5, 8, "ana")).toEqual({
      value: "hola @ana  qué",
      caret: 10,
    });
  });
});

describe("liveTeam", () => {
  it("lists team mentions not removed", () => {
    const luis = { ...ana, id: 2, username: "luis" };
    const eva = { ...ana, id: 3, username: "eva" };
    expect(liveTeam({ mentions: [m(ana, "team"), m(luis, "team", true), m(eva)] })).toEqual([ana]);
  });
});

it("uses no regex lookbehind (old iOS Safari throws on it)", () => {
  expect(MENTION_SOURCE).not.toContain("(?<");
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend && npx vitest run src/lib/mentions.test.ts`
Expected: FAIL — cannot resolve `./mentions`.

- [ ] **Step 3: Types**

In `frontend/src/lib/types.ts`:

```ts
export interface Mention {
  user: Author;
  kind: "social" | "team";
  /** The teacher took this member off the team. */
  removed: boolean;
}

export interface TeamMember {
  user: QueueStudent;
  removed: boolean;
}

export interface TeamCheckResult {
  username: string;
  status: "ok" | "unknown" | "self" | "author_inactive" | "not_in_class" | "on_team" | "max_team";
  team_author: string | null;
}
```

Add `mentions?: Mention[];` to `Post` (after `is_submission`), `team: TeamMember[];` to `EntregaRow`, and `team_of: QueueStudent | null;` to the examen roster row type.

- [ ] **Step 4: `mentions.ts`**

```ts
// frontend/src/lib/mentions.ts
import type { Author, Mention, Post } from "./types";

/** Same rule as backend/app/services/mentions.py. No lookbehind: iOS Safari
 *  before 16.4 throws on it when the module loads. The leading group eats
 *  the character before the @ instead. */
export const MENTION_SOURCE = "(^|[^A-Za-z0-9_@])@([A-Za-z0-9_]{3,20})(?![A-Za-z0-9_])";

export type Segment = { text: string } | { mention: Author };

export function parseUsernames(content: string): string[] {
  const out: string[] = [];
  for (const m of content.matchAll(new RegExp(MENTION_SOURCE, "g"))) {
    const name = m[2].toLowerCase();
    if (!out.includes(name)) out.push(name);
  }
  return out;
}

export function splitMentions(content: string, mentions: Mention[] = []): Segment[] {
  const byName = new Map(
    mentions
      .filter((x) => x.user.username)
      .map((x) => [x.user.username!.toLowerCase(), x.user]),
  );
  const out: Segment[] = [];
  let last = 0;
  for (const m of content.matchAll(new RegExp(MENTION_SOURCE, "g"))) {
    const user = byName.get(m[2].toLowerCase());
    if (!user) continue;
    const at = m.index! + m[1].length;
    if (at > last) out.push({ text: content.slice(last, at) });
    out.push({ mention: user });
    last = at + 1 + m[2].length;
  }
  if (last < content.length || out.length === 0) out.push({ text: content.slice(last) });
  return out;
}

/** The @word being typed at the caret, if any. */
export function activeMention(
  value: string,
  caret: number,
): { start: number; query: string } | null {
  let i = caret - 1;
  while (i >= 0 && /[A-Za-z0-9_]/.test(value[i])) i--;
  if (i < 0 || value[i] !== "@") return null;
  if (i > 0 && /[A-Za-z0-9_@]/.test(value[i - 1])) return null;
  const query = value.slice(i + 1, caret);
  if (query.length < 1 || query.length > 20) return null;
  return { start: i, query };
}

export function insertMention(
  value: string,
  start: number,
  caret: number,
  username: string,
): { value: string; caret: number } {
  const inserted = `@${username} `;
  return {
    value: value.slice(0, start) + inserted + value.slice(caret),
    caret: start + inserted.length,
  };
}

/** Members a submission still counts for, besides its author. */
export function liveTeam(post: Pick<Post, "mentions">): Author[] {
  return (post.mentions ?? [])
    .filter((x) => x.kind === "team" && !x.removed)
    .map((x) => x.user);
}
```

- [ ] **Step 5: `useDebounced.ts`**

```ts
// frontend/src/lib/useDebounced.ts
import { useEffect, useState } from "react";

/** `value`, once it has stopped changing for `ms`. */
export function useDebounced<T>(value: T, ms = 250): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return settled;
}
```

- [ ] **Step 6: Run tests, typecheck**

Run: `cd frontend && npx vitest run src/lib/mentions.test.ts && npx tsc -b`
Expected: PASS. `tsc` may flag places that build `EntregaRow` / roster rows in tests or code — add `team: []` / `team_of: null` there.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/mentions.ts frontend/src/lib/mentions.test.ts frontend/src/lib/useDebounced.ts
git commit -m "feat(mentions): client parsing, segments and caret helpers"
```

---

### Task 9: Mentions in posts, and autocomplete in both composers

**Files:**
- Create: `frontend/src/components/MentionText.tsx`
- Create: `frontend/src/components/MentionSuggestions.tsx`
- Create (via CLI): `frontend/src/components/ui/popover.tsx`
- Modify: `frontend/src/components/PostCard.tsx`, `frontend/src/pages/Compose.tsx`, `frontend/src/pages/Thread.tsx`, `frontend/src/strings/es.ts`

**Interfaces:**
- Consumes: `splitMentions`, `liveTeam`, `activeMention`, `insertMention`, `useDebounced` (Task 8); `GET /api/users/search` (Task 5).
- Produces: `<MentionText content mentions />`; `<MentionSuggestions value caret anchor onPick />` where `onPick(next: { value: string; caret: number })`.

- [ ] **Step 1: Strings**

In `frontend/src/strings/es.ts`, add a `mentions` section (placeholders; Mario writes final copy):

```ts
  mentions: {
    team: "Equipo:",
    maxTeam: "@{user} no cuenta: el equipo es de máximo 3",
    notInClass: "@{user} no está en esta clase",
    onTeam: "@{user} ya entregó con el equipo de @{author}",
    unknown: "@{user} no existe",
    authorInactive: "Tu entrega no forma equipo: no estás activo en esta clase",
    teamResult: "Equipo: {users}",
    teamAlone: "Entregaste sin equipo",
    inTeamWith: "en equipo con",
    removeFromTeam: "Quitar del equipo",
    restoreToTeam: "Devolver al equipo",
    removeConfirm: "@{user} deja de recibir esta calificación; vuelve a contar su entrega anterior, si tiene.",
    removed: "fuera del equipo",
    confirm: "Quitar",
    cancel: "Cancelar",
    teamError: "No se pudo cambiar el equipo",
  },
```

- [ ] **Step 2: `MentionText`**

```tsx
// frontend/src/components/MentionText.tsx
import UserLink from "@/components/UserLink";
import { splitMentions } from "@/lib/mentions";
import type { Mention } from "@/lib/types";

/** Post text with each resolved @mention as a UserLink. An @word the server
 *  didn't resolve stays text — never a dead link. The span stops the tap from
 *  also reaching a card-level "open thread" handler. */
export default function MentionText({
  content,
  mentions,
}: {
  content: string;
  mentions?: Mention[];
}) {
  return (
    <>
      {splitMentions(content, mentions).map((s, i) =>
        "mention" in s ? (
          <span key={i} onClick={(e) => e.stopPropagation()}>
            <UserLink user={s.mention} className="font-medium" />
          </span>
        ) : (
          <span key={i}>{s.text}</span>
        ),
      )}
    </>
  );
}
```

- [ ] **Step 3: PostCard renders mentions and the team line**

In `frontend/src/components/PostCard.tsx`:

1. Replace `{post.content}` inside `body` with `<MentionText content={post.content} mentions={post.mentions} />`.
2. A link inside the feed's `<Link>` wrapper would nest anchors. Replace the `linkToThread && !removed ? (<Link …>{body}</Link>)` branch with a click target that is not an anchor:

```tsx
        {linkToThread && !removed ? (
          <div
            role="link"
            tabIndex={0}
            className="mt-1 block cursor-pointer"
            onClick={() => navigate(`/post/${post.id}`)}
            onKeyDown={(e) => {
              if (e.key === "Enter") navigate(`/post/${post.id}`);
            }}
          >
            {body}
          </div>
        ) : (
          <div className="mt-1">{body}</div>
        )}
```

with `const navigate = useNavigate();` (from `react-router-dom`) at the top of the component; drop the `Link` import if unused.

3. Under the body (before attachments), the team line for a submission with a live team:

```tsx
        {!removed && liveTeam(post).length > 0 && (
          <p className="mt-1 flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
            <span>{es.mentions.team}</span>
            {[post.author, ...liveTeam(post)].map((u, i) => (
              <span key={u.id} className="flex items-center gap-1">
                {i > 0 && <span aria-hidden>·</span>}
                <UserLink user={u} />
              </span>
            ))}
          </p>
        )}
```

- [ ] **Step 4: Add the popover primitive**

Run: `cd frontend && npx shadcn add popover`
Expected: creates `src/components/ui/popover.tsx` (base-sera on `@base-ui/react`). Do not edit it. Read it to learn the exported names and whether `PopoverContent` forwards `anchor`, `side`, `initialFocus` and `finalFocus` to base-ui's `Popover.Positioner` / `Popover.Popup`.

- [ ] **Step 5: `MentionSuggestions`**

```tsx
// frontend/src/components/MentionSuggestions.tsx
import type { RefObject } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { activeMention, insertMention } from "@/lib/mentions";
import { useDebounced } from "@/lib/useDebounced";
import { Popover, PopoverContent } from "@/components/ui/popover";
import UserLink from "@/components/UserLink";
import type { Author } from "@/lib/types";

/** @-autocomplete above a composer field. Never takes focus: on a phone,
 *  moving focus closes the keyboard mid-word. */
export default function MentionSuggestions({
  value,
  caret,
  anchor,
  onPick,
}: {
  value: string;
  caret: number;
  anchor: RefObject<HTMLElement | null>;
  onPick: (next: { value: string; caret: number }) => void;
}) {
  const active = activeMention(value, caret);
  const query = useDebounced(active?.query ?? "", 200);
  const q = useQuery({
    queryKey: ["user-search", query],
    queryFn: () =>
      api<{ users: Author[] }>(`/api/users/search?q=${encodeURIComponent(query)}`),
    enabled: query.length > 0,
    staleTime: 30_000,
  });
  const users = active && query === active.query ? (q.data?.users ?? []) : [];
  return (
    <Popover open={users.length > 0} modal={false}>
      <PopoverContent
        anchor={anchor}
        side="top"
        align="start"
        initialFocus={false}
        finalFocus={false}
        className="w-64 p-1"
      >
        <ul>
          {users.map((u) => (
            <li key={u.id}>
              <button
                type="button"
                // pointerdown + preventDefault keeps focus (and the keyboard)
                // on the field.
                onPointerDown={(e) => {
                  e.preventDefault();
                  onPick(insertMention(value, active!.start, caret, u.username!));
                }}
                className="flex w-full items-center gap-2 px-2 py-2 text-left text-sm"
              >
                <UserLink user={u} avatar size={24} plain />
                <UserLink user={u} plain />
                <span className="truncate text-muted-foreground">{u.name}</span>
              </button>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
```

If Step 4 showed that the generated `PopoverContent` does not forward `anchor`/`initialFocus`/`finalFocus`, pass them where the generated file exposes base-ui's `Positioner` and `Popup` props (e.g. a `positionerProps` prop or by composing `PopoverPrimitive.Positioner` the same way the generated file does) — still without editing `ui/popover.tsx`.

- [ ] **Step 6: Wire it into both composers**

`Compose.tsx` — track the caret and anchor on the textarea:

```tsx
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  const [caret, setCaret] = useState(0);
  // …
      <textarea
        ref={fieldRef}
        /* existing props */
        onChange={(e) => {
          setContent(e.target.value);
          setCaret(e.target.selectionStart ?? e.target.value.length);
        }}
        onSelect={(e) => setCaret(e.currentTarget.selectionStart ?? 0)}
      />
      <MentionSuggestions
        value={content}
        caret={caret}
        anchor={fieldRef}
        onPick={({ value, caret: c }) => {
          setContent(value);
          setCaret(c);
          requestAnimationFrame(() => fieldRef.current?.setSelectionRange(c, c));
        }}
      />
```

`Thread.tsx` — the same on the reply `<input>` (`ref={fieldRef}` as `HTMLInputElement`, `reply`/`setReply`).

- [ ] **Step 7: Verify**

Run: `cd frontend && npx tsc -b && npx vitest run && npx eslint src && npm run build`
Expected: all pass. Then run the app (`/run` skill or `npm run dev` with the backend) at a 390 px viewport: type `@a` in the composer and in a thread reply — the list appears above the field, the keyboard/focus stays in the field, tapping a name inserts `@username `. A posted `@username` is tappable in the feed and the thread, and tapping it opens the profile, not the thread.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/MentionText.tsx frontend/src/components/MentionSuggestions.tsx frontend/src/components/ui/popover.tsx frontend/src/components/PostCard.tsx frontend/src/pages/Compose.tsx frontend/src/pages/Thread.tsx frontend/src/strings/es.ts frontend/package.json frontend/package-lock.json
git commit -m "feat(mentions): @ links in posts and autocomplete in composers"
```

---

### Task 10: Team warnings in the submission composer

**Files:**
- Create: `frontend/src/lib/teamWarnings.ts`, `frontend/src/lib/teamWarnings.test.ts`
- Modify: `frontend/src/pages/Thread.tsx`

**Interfaces:**
- Consumes: `parseUsernames`, `useDebounced`, `TeamCheckResult` (Task 8); `GET /api/posts/{id}/team-check` (Task 5); `es.mentions` (Task 9).
- Produces: `teamWarning(r: TeamCheckResult): string | null`; `teamResultToast(expected: string[], sent: Post): string | null`.

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/lib/teamWarnings.test.ts
import { describe, expect, it } from "vitest";
import { teamResultToast, teamWarning } from "./teamWarnings";
import type { Post } from "./types";

describe("teamWarning", () => {
  it("is null when the mention joins", () => {
    expect(teamWarning({ username: "ana", status: "ok", team_author: null })).toBeNull();
  });
  it("names the team someone is already on", () => {
    expect(
      teamWarning({ username: "pedro", status: "on_team", team_author: "ana" }),
    ).toBe("@pedro ya entregó con el equipo de @ana");
  });
  it("says nothing about a self-mention", () => {
    expect(teamWarning({ username: "yo", status: "self", team_author: null })).toBeNull();
  });
});

describe("teamResultToast", () => {
  const sent = (team: string[]) =>
    ({
      mentions: team.map((u, i) => ({
        user: { id: i, username: u, name: u, avatar_url: null, role: "student" },
        kind: "team",
        removed: false,
      })),
    }) as unknown as Post;
  it("is silent when publish matched the check", () => {
    expect(teamResultToast(["ana"], sent(["ana"]))).toBeNull();
  });
  it("says who ended up on the team when it changed", () => {
    expect(teamResultToast(["ana", "luis"], sent(["ana"]))).toBe("Equipo: @ana");
  });
  it("says when nobody did", () => {
    expect(teamResultToast(["ana"], sent([]))).toBe("Entregaste sin equipo");
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend && npx vitest run src/lib/teamWarnings.test.ts`
Expected: FAIL — cannot resolve `./teamWarnings`.

- [ ] **Step 3: Implement**

```ts
// frontend/src/lib/teamWarnings.ts
import { es } from "@/strings/es";
import { liveTeam } from "./mentions";
import type { Post, TeamCheckResult } from "./types";

/** The warning under the submission composer for one @, or null if it joins
 *  (or is the author — nothing to say). Warnings never block sending. */
export function teamWarning(r: TeamCheckResult): string | null {
  const t = es.mentions;
  const fill = (s: string) =>
    s.replace("{user}", r.username).replace("{author}", r.team_author ?? "");
  switch (r.status) {
    case "ok":
    case "self":
      return null;
    case "max_team":
      return fill(t.maxTeam);
    case "not_in_class":
      return fill(t.notInClass);
    case "on_team":
      return fill(t.onTeam);
    case "unknown":
      return fill(t.unknown);
    case "author_inactive":
      return t.authorInactive;
  }
}

/** Publish re-decides the team; if it differs from the last check, say who
 *  ended up on it. */
export function teamResultToast(expected: string[], sent: Post): string | null {
  const got = liveTeam(sent).map((u) => u.username ?? "");
  const same =
    got.length === expected.length && got.every((u) => expected.includes(u));
  if (same) return null;
  if (got.length === 0) return es.mentions.teamAlone;
  return es.mentions.teamResult.replace("{users}", got.map((u) => `@${u}`).join(" · "));
}
```

- [ ] **Step 4: Wire into `Thread.tsx`**

```tsx
  // A submission: the entrega switch on, or an examen reply with files.
  // Hooks run before the early returns, so read the root from q.data.
  const isSubmission =
    replyTo === null &&
    (isEntrega || (q.data?.post.type === "examen" && files.length > 0));
  const teamNames = useDebounced(
    isSubmission ? parseUsernames(reply).join(",") : "",
    300,
  );
  const teamCheck = useQuery({
    queryKey: ["team-check", id, teamNames],
    queryFn: () =>
      api<{ results: TeamCheckResult[] }>(
        `/api/posts/${id}/team-check?` +
          teamNames.split(",").map((u) => `u=${encodeURIComponent(u)}`).join("&"),
      ),
    enabled: teamNames !== "",
  });
  const okTeam = (teamCheck.data?.results ?? [])
    .filter((r) => r.status === "ok")
    .map((r) => r.username);
```

(place these right after the `q` query, above the early returns). In `send.onSuccess`, after the existing work:

```tsx
      if (isSubmission && teamNames !== "") {
        const msg = teamResultToast(okTeam, sent);
        if (msg) toast.show(msg);
      }
```

In the form, above `<FileChips …>`:

```tsx
        {isSubmission && teamCheck.data && (
          <div className="mb-1 flex flex-col gap-0.5 text-xs">
            {okTeam.length > 0 && (
              <p className="text-muted-foreground">
                {es.mentions.team}{" "}
                {okTeam.map((u) => `@${u}`).join(" · ")}
              </p>
            )}
            {teamCheck.data.results.map((r) => {
              const w = teamWarning(r);
              return w ? (
                <p key={r.username} className="text-destructive">{w}</p>
              ) : null;
            })}
          </div>
        )}
```

- [ ] **Step 5: Verify**

Run: `cd frontend && npx vitest run && npx tsc -b && npx eslint src`
Expected: PASS. In the running app at 390 px, on a tarea thread with the entrega switch on, type `@` + three classmates: the line shows the first two, and a warning names the third. The reply bar grows; confirm the list's `pb-28`/`pb-52` padding still keeps the last reply visible (bump the padding when warnings show if not).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/teamWarnings.ts frontend/src/lib/teamWarnings.test.ts frontend/src/pages/Thread.tsx
git commit -m "feat(teams): warn in the composer which @ won't join the team"
```

---

### Task 11: Teacher UI — team in the grading sheet, `/revisar` and the roster

**Files:**
- Create: `frontend/src/components/TeamEditor.tsx`
- Modify: `frontend/src/components/ReviewSheet.tsx`, `frontend/src/pages/Thread.tsx`, `frontend/src/pages/Revisar.tsx`, `frontend/src/components/ExamenRoster.tsx`, `frontend/src/lib/review.ts`

**Interfaces:**
- Consumes: `TeamMember`, `EntregaRow.team`, roster `team_of` (Task 8); remove/restore endpoints (Task 6); `es.mentions` (Task 9).
- Produces: `setTeamMember(postId: number, userId: number, removed: boolean): Promise<Post>` in `lib/review.ts`; `<TeamEditor postId members onChanged />`; `ReviewSheet` prop `team?: { postId: number; members: TeamMember[] }`.

- [ ] **Step 1: API helper**

In `frontend/src/lib/review.ts`:

```ts
export function setTeamMember(postId: number, userId: number, removed: boolean) {
  return api<Post>(
    `/api/posts/${postId}/team/${userId}/${removed ? "remove" : "restore"}`,
    { method: "POST" },
  );
}
```

(import `Post` type if not already).

- [ ] **Step 2: `TeamEditor`**

```tsx
// frontend/src/components/TeamEditor.tsx
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ApiError } from "@/lib/api";
import { setTeamMember } from "@/lib/review";
import { Button } from "@/components/ui/button";
import UserLink from "@/components/UserLink";
import { useToast } from "@/components/Toaster";
import { es } from "@/strings/es";
import type { TeamMember } from "@/lib/types";

/** The team inside the grading sheet. Removing a member is a flag the
 *  teacher can undo — never a different grade (one grade per entrega). */
export default function TeamEditor({
  postId,
  members,
  onChanged,
}: {
  postId: number;
  members: TeamMember[];
  onChanged: () => void;
}) {
  const toast = useToast();
  const [confirming, setConfirming] = useState<number | null>(null);
  const flip = useMutation({
    mutationFn: ({ userId, removed }: { userId: number; removed: boolean }) =>
      setTeamMember(postId, userId, removed),
    onSuccess: () => {
      setConfirming(null);
      onChanged();
    },
    onError: (e) => toast.show(e instanceof ApiError ? e.message : es.mentions.teamError),
  });
  if (members.length === 0) return null;
  return (
    <div className="mt-4 flex flex-col gap-2">
      <p className="text-xs text-muted-foreground">{es.mentions.team}</p>
      {members.map((m) => (
        <div key={m.user.id} className="flex flex-col gap-1">
          <div className="flex items-center justify-between gap-3 text-sm">
            <span className={m.removed ? "text-muted-foreground line-through" : ""}>
              <UserLink user={m.user} plain />
            </span>
            {m.removed ? (
              <Button
                variant="outline"
                size="sm"
                disabled={flip.isPending}
                onClick={() => flip.mutate({ userId: m.user.id, removed: false })}
              >
                {es.mentions.restoreToTeam}
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                disabled={flip.isPending}
                onClick={() => setConfirming(m.user.id)}
              >
                {es.mentions.removeFromTeam}
              </Button>
            )}
          </div>
          {confirming === m.user.id && (
            <div className="flex flex-col gap-2 border p-2 text-xs">
              <p>
                {es.mentions.removeConfirm.replace("{user}", m.user.username ?? m.user.name)}
              </p>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => flip.mutate({ userId: m.user.id, removed: true })}
              >
                {es.mentions.confirm}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setConfirming(null)}>
                {es.mentions.cancel}
              </Button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
```

Check `components/ui/button.tsx` for the available `variant`/`size` names (`outline`, `destructive`, `ghost`, `sm`); use the closest existing ones.

- [ ] **Step 3: `ReviewSheet` shows the team**

Add the optional prop `team?: { postId: number; members: TeamMember[] }` and an `onTeamChanged?: () => void`. Render under the student name:

```tsx
        {team && (
          <TeamEditor
            postId={team.postId}
            members={team.members}
            onChanged={() => onTeamChanged?.()}
          />
        )}
```

- [ ] **Step 4: Thread passes the team**

In `Thread.tsx`, on `<ReviewSheet …>`:

```tsx
          team={{
            postId: grading.id,
            members: (grading.mentions ?? [])
              .filter((m) => m.kind === "team")
              .map((m) => ({ user: m.user, removed: m.removed })),
          }}
          onTeamChanged={() => {
            void qc.invalidateQueries({ queryKey: ["thread", id] });
            void qc.invalidateQueries({ queryKey: ["examen-roster", post.id] });
            invalidateGrades(qc);
            // `grading` is a snapshot of the reply; close so the teacher
            // reopens it with the refetched team.
            setGrading(null);
          }}
```

- [ ] **Step 5: `/revisar` rows show the team**

In `Revisar.tsx` Entregas list, after `<UserLink user={row.student} …/>`:

```tsx
                {row.team.filter((m) => !m.removed).map((m) => (
                  <span key={m.user.id} className="flex items-center py-3 pr-2 text-sm">
                    <span aria-hidden className="pr-1 text-muted-foreground">·</span>
                    <UserLink user={m.user} />
                  </span>
                ))}
```

and pass `team={{ postId: open.row.entrega_post_id, members: open.row.team }}` plus `onTeamChanged={() => { onSaved(); setOpen(null); }}` to its `ReviewSheet`.

- [ ] **Step 6: Roster says "en equipo con"**

In `ExamenRoster.tsx`, under the student name:

```tsx
              {r.team_of && (
                <span className="text-xs text-muted-foreground">
                  {es.mentions.inTeamWith} <UserLink user={r.team_of} plain />
                </span>
              )}
```

After a score saves (`save.onSuccess`), invalidate `["examen-roster", examenId]` so all members' rows show the shared score:

```tsx
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["examen-roster", examenId] });
    },
```

- [ ] **Step 7: Verify**

Run: `cd frontend && npx tsc -b && npx vitest run && npx eslint src && npm run build`
Expected: PASS. In the app at 390 px as teacher: open a team entrega's grading sheet from the thread and from `/revisar` — the team shows; "Quitar del equipo" asks to confirm, then the member is struck through with "Devolver al equipo"; `/revisar` shows one row for the team; the examen roster shows "en equipo con @ana" with the shared score after saving any member's row.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/TeamEditor.tsx frontend/src/components/ReviewSheet.tsx frontend/src/pages/Thread.tsx frontend/src/pages/Revisar.tsx frontend/src/components/ExamenRoster.tsx frontend/src/lib/review.ts
git commit -m "feat(teams): teacher sees and edits the team where grading happens"
```

---

### Task 12: Planning docs

**Files:**
- Modify: `planning/roadmap.md`, `planning/changelog.md`

- [ ] **Step 1: Roadmap**

In `planning/roadmap.md`: mark "Menciones y entregas en equipo" ✅ with the date, link the spec, and in "▶ Empieza aquí" move it to done so **Racha** is next. Record any rulings made during execution under the section.

- [ ] **Step 2: Changelog**

Add a dated entry at the top of `planning/changelog.md` (Spanish, tú): `@` with autocomplete anywhere; an entrega that `@`s up to 2 classmates is the whole team's — one grade, one item to grade; first team wins; quitar/devolver del equipo; what Pedro sees.

- [ ] **Step 3: Commit**

```bash
git add planning/roadmap.md planning/changelog.md
git commit -m "docs(planning): menciones y entregas en equipo shipped"
```
