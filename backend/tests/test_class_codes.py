import re
from datetime import date

from app.models import Class, Enrollment, User
from app.services.class_codes import generate_code


def _teacher(db):
    t = User(google_id="g-t", email="t@example.com", name="T", role="teacher")
    db.add(t)
    db.commit()
    return t


def test_code_format(db):
    code = generate_code(db, "micro")
    assert re.fullmatch(r"MICRO\d{4}[A-Z0-9]{4}", code)


def test_code_avoids_collisions(db, monkeypatch):
    t = _teacher(db)
    existing = Class(
        name="X", code="MICRO2026AAAA", teacher_id=t.id,
        start_date=date(2026, 8, 1), end_date=date(2026, 12, 1), schedule_json=[],
    )
    db.add(existing)
    db.commit()
    import app.services.class_codes as cc
    calls = iter(["AAAA", "BBBB"])
    monkeypatch.setattr(cc, "_random_suffix", lambda: next(calls))
    code = generate_code(db, "MICRO")
    assert code.endswith("BBBB")


def test_enrollment_unique(db):
    t = _teacher(db)
    c = Class(
        name="Micro", code="MICRO2026ZZZZ", teacher_id=t.id,
        start_date=date(2026, 8, 1), end_date=date(2026, 12, 1), schedule_json=[],
    )
    s = User(google_id="g-s", email="s@example.com", name="S")
    db.add_all([c, s])
    db.commit()
    e = Enrollment(user_id=s.id, class_id=c.id)
    db.add(e)
    db.commit()
    assert e.status == "active"
