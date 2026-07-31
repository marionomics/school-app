from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models import AttendanceRecord, ClassSession, Post, PointsLedger, Review
from app.routers.grades import round_grade
from app.services.grades import (calculate_grade, counting_review, faltas_breakdown,
                                 get_config, lateness_score, ledger_breakdown,
                                 like_points, tareas_rubro)

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


def test_round_grade_uses_half_up_not_bankers_rounding():
    # 27.005 sits exactly on the .xx5 boundary: ROUND_HALF_EVEN (Python's
    # `round()` default for Decimal) gives 27.00 here; ROUND_HALF_UP, which
    # the spec requires, gives 27.01. A value that rounds the same way under
    # both modes would prove nothing about which mode is actually wired up.
    assert round(Decimal("27.005"), 2) == Decimal("27.00")   # sanity: banker's rounding
    assert round_grade(Decimal("27.005")) == Decimal("27.01")


def test_deleted_entrega_falls_back_to_zero(db, student, teacher, klass, enrolled):
    t = _tarea(db, teacher, klass, DUE)
    e = _entrega(db, student, t, DUE - timedelta(hours=1))
    e.status = "deleted"
    db.commit()
    r = tareas_rubro(db, student.id, klass, now=DUE + timedelta(days=1))
    assert r.points == Decimal("0")


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
