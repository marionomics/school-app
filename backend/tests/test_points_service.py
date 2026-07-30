from decimal import Decimal

from app.models import Like, Post, PointsLedger
from app.services import points


def _post(db, author, klass=None, type_="regular", taps=None):
    p = Post(author_id=author.id, content="x", type=type_, taps=taps,
             class_id=klass.id if klass else None)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_award_participacion(db, student, klass, enrolled):
    p = _post(db, student, klass, "participacion", taps=3)
    row = points.award_participacion(db, p)
    db.commit()
    assert row.points == Decimal("3.0")
    assert row.source_type == "participacion" and row.source_id == p.id
    assert row.class_id == klass.id


def test_award_is_idempotent(db, student, klass, enrolled):
    p = _post(db, student, klass, "participacion", taps=1)
    r1 = points.award_participacion(db, p)
    r2 = points.award_participacion(db, p)
    db.commit()
    assert r1.id == r2.id
    assert db.query(PointsLedger).count() == 1


def test_no_award_without_class(db, student, enrolled):
    p = _post(db, student, None, "participacion", taps=2)
    assert points.award_participacion(db, p) is None


def test_no_award_for_ghost(db, ghost, klass):
    p = _post(db, ghost, klass, "participacion", taps=1)
    assert points.award_participacion(db, p) is None


def test_no_award_for_teacher_recipient(db, teacher, student, klass):
    # A real liker row: PostgreSQL enforces likes.user_id's FK, SQLite does not.
    p = _post(db, teacher, klass)
    like_row = Like(user_id=student.id, post_id=p.id)
    db.add(like_row)
    db.commit()
    assert points.award_like(db, like=like_row, post=p, liker=student) is None


def test_like_award_and_revoke_cycle(db, student, student2, klass, enrolled):
    p = _post(db, student, klass)
    like = Like(user_id=student2.id, post_id=p.id)
    db.add(like)
    db.commit()
    row = points.award_like(db, like=like, post=p, liker=student2)
    db.commit()
    assert row.points == Decimal("1.0")
    n = points.revoke_like(db, like_id=like.id, revoked_by=student2.id)
    db.commit()
    assert n == 1
    db.refresh(row)
    assert row.revoked_at is not None and row.revoked_by == student2.id
    # Hard-delete the like to mirror the real unlike flow (Task 6)
    db.delete(like)
    db.commit()
    # re-like awards a fresh row
    like2 = Like(user_id=student2.id, post_id=p.id)
    db.add(like2)
    db.commit()
    row2 = points.award_like(db, like=like2, post=p, liker=student2)
    db.commit()
    assert row2.id != row.id and row2.revoked_at is None


def test_teacher_liker_awards_nothing(db, student, teacher, klass, enrolled):
    p = _post(db, student, klass)
    like = Like(user_id=teacher.id, post_id=p.id)
    db.add(like)
    db.commit()
    assert points.award_like(db, like=like, post=p, liker=teacher) is None


def test_revoke_post_revokes_everything(db, student, student2, teacher, klass, enrolled):
    p = _post(db, student, klass, "participacion", taps=2)
    points.award_participacion(db, p)
    like = Like(user_id=student2.id, post_id=p.id)
    db.add(like)
    db.commit()
    points.award_like(db, like=like, post=p, liker=student2)
    db.commit()
    n = points.revoke_post(db, post=p, revoked_by=teacher.id)
    db.commit()
    assert n == 2
    assert db.query(PointsLedger).filter(PointsLedger.revoked_at.is_(None)).count() == 0
