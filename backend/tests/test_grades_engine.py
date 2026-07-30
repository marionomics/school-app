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
