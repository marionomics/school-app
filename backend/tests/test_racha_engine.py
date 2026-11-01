from decimal import Decimal

from app.models import Enrollment, Like, PointsLedger, Post, PostRoll, User
from app.services.grades import ledger_breakdown, like_points


def _fans(db, klass, n):
    out = []
    for i in range(n):
        u = User(google_id=f"g-f{i}", email=f"f{i}@example.com", name=f"F{i}")
        db.add(u)
        db.flush()
        db.add(Enrollment(user_id=u.id, class_id=klass.id))
        out.append(u)
    db.commit()
    return out


def _post(db, author, klass, multiplier=None):
    p = Post(author_id=author.id, class_id=klass.id, content="x" * 30)
    db.add(p)
    db.flush()
    if multiplier is not None:
        db.add(PostRoll(post_id=p.id, multiplier=multiplier, streak_days=7, x2=0, x3=0))
    db.commit()
    return p


def _like(db, fan, post):
    like = Like(user_id=fan.id, post_id=post.id)
    db.add(like)
    db.flush()
    row = PointsLedger(user_id=post.author_id, class_id=post.class_id,
                       source_type="forum_like", source_id=like.id, points=Decimal("1"))
    db.add(row)
    db.commit()
    return like, row


def test_a_triple_posts_auras_weigh_three(db, student, klass, enrolled):
    fans = _fans(db, klass, 5)
    triple = _post(db, student, klass, multiplier=3)
    plain = _post(db, student, klass)
    for f in fans[:4]:
        _like(db, f, triple)
    _like(db, fans[4], plain)
    out = ledger_breakdown(db, student.id, klass.id)
    assert out["likes_count"] == 5
    assert out["likes_weighted"] == 13
    assert out["likes"] == like_points(13, Decimal("1.0"), Decimal("0.5"))


def test_a_post_without_a_roll_and_a_one_x_roll_count_once(db, student, klass, enrolled):
    fans = _fans(db, klass, 2)
    _like(db, fans[0], _post(db, student, klass))
    _like(db, fans[1], _post(db, student, klass, multiplier=1))
    assert ledger_breakdown(db, student.id, klass.id)["likes_weighted"] == 2


def test_an_unlike_drops_the_weighted_count_by_the_multiplier(db, student, klass, enrolled):
    from app.models import utcnow
    fans = _fans(db, klass, 2)
    double = _post(db, student, klass, multiplier=2)
    _like(db, fans[0], double)
    _, row = _like(db, fans[1], double)
    assert ledger_breakdown(db, student.id, klass.id)["likes_weighted"] == 4
    row.revoked_at = utcnow()
    db.commit()
    assert ledger_breakdown(db, student.id, klass.id)["likes_weighted"] == 2


def test_a_triple_in_class_a_leaves_class_b_unchanged(db, student, teacher, klass, enrolled):
    from datetime import date
    from app.models import Class
    b = Class(name="Macro", code="MACRO2026TEST", teacher_id=teacher.id,
              start_date=date(2026, 8, 17), end_date=date(2026, 12, 4))
    db.add(b)
    db.commit()
    db.add(Enrollment(user_id=student.id, class_id=b.id))
    db.commit()
    fans = _fans(db, klass, 3)
    pa = _post(db, student, klass, multiplier=3)
    pb = _post(db, student, b)
    for f in fans:
        _like(db, f, pa)
        _like(db, f, pb)
    out_a = ledger_breakdown(db, student.id, klass.id)
    out_b = ledger_breakdown(db, student.id, b.id)
    assert out_a["likes_count"] == 3 and out_a["likes_weighted"] == 9
    assert out_b["likes_count"] == 3 and out_b["likes_weighted"] == 3
