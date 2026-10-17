from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.models import Class, Enrollment
from app.services.attribution import resolve_default_class

TZ = ZoneInfo("America/Mexico_City")
# Wednesday 2026-10-14. weekday(): Monday 0 … Wednesday 2.
WED = date(2026, 10, 14)


def _at(day: date, hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime(day.year, day.month, day.day, h, m, tzinfo=TZ)


def _class(db, teacher, code, schedule, start=date(2026, 8, 17), end=date(2026, 12, 4)):
    k = Class(name=code, code=code, teacher_id=teacher.id, start_date=start,
              end_date=end, schedule_json=schedule)
    db.add(k)
    db.commit()
    return k


def recent(db, user, now):
    return resolve_default_class(db, user, now=now, fallback_to_recent=True)


def _enroll(db, student, *classes):
    for k in classes:
        db.add(Enrollment(user_id=student.id, class_id=k.id))
    db.commit()


def test_in_session_class_wins(db, teacher, student):
    a = _class(db, teacher, "A", [{"day": 2, "start": "10:00", "end": "11:00"}])
    b = _class(db, teacher, "B", [{"day": 2, "start": "18:00", "end": "19:00"}])
    _enroll(db, student, a, b)
    assert resolve_default_class(db, student, now=_at(WED, "10:30")) == a.id


def test_out_of_hours_falls_to_the_class_you_had_most_recently(db, teacher, student):
    # Before this, two classes and none in session meant None — and the aura
    # that post received counted for nobody.
    a = _class(db, teacher, "A", [{"day": 2, "start": "10:00", "end": "11:00"}])
    b = _class(db, teacher, "B", [{"day": 2, "start": "18:00", "end": "19:00"}])
    _enroll(db, student, a, b)
    assert recent(db, student, now=_at(WED, "21:00")) == b.id
    assert recent(db, student, now=_at(WED, "14:00")) == a.id


def test_most_recent_wraps_back_into_last_week(db, teacher, student):
    # Monday 08:00, before anything this week: Friday's class is the latest.
    mon = date(2026, 10, 12)
    a = _class(db, teacher, "A", [{"day": 2, "start": "10:00", "end": "11:00"}])
    b = _class(db, teacher, "B", [{"day": 4, "start": "10:00", "end": "11:00"}])
    _enroll(db, student, a, b)
    assert recent(db, student, now=_at(mon, "08:00")) == b.id


def test_a_finished_class_does_not_outrank_one_in_term(db, teacher, student):
    old = _class(db, teacher, "OLD", [{"day": 2, "start": "18:00", "end": "19:00"}],
                 start=date(2026, 1, 12), end=date(2026, 5, 29))
    cur = _class(db, teacher, "CUR", [{"day": 2, "start": "10:00", "end": "11:00"}])
    _enroll(db, student, old, cur)
    assert recent(db, student, now=_at(WED, "21:00")) == cur.id


def test_without_schedules_the_newest_class_wins(db, teacher, student):
    a = _class(db, teacher, "A", [])
    b = _class(db, teacher, "B", [])
    _enroll(db, student, a, b)
    assert recent(db, student, now=_at(WED, "21:00")) == b.id


def test_single_class_and_no_classes(db, teacher, student):
    assert resolve_default_class(db, student, now=_at(WED, "21:00")) is None
    a = _class(db, teacher, "A", [])
    _enroll(db, student, a)
    assert resolve_default_class(db, student, now=_at(WED, "21:00")) == a.id


def test_teacher_gets_the_classes_they_teach(db, teacher):
    a = _class(db, teacher, "A", [{"day": 2, "start": "10:00", "end": "11:00"}])
    b = _class(db, teacher, "B", [{"day": 2, "start": "18:00", "end": "19:00"}])
    assert recent(db, teacher, now=_at(WED, "20:00")) == b.id
    assert a.id != b.id


def test_without_the_fallback_ambiguity_still_means_ask(db, teacher, student):
    # A tarea or examen must never land in a guessed class.
    a = _class(db, teacher, "A", [{"day": 2, "start": "10:00", "end": "11:00"}])
    b = _class(db, teacher, "B", [{"day": 2, "start": "18:00", "end": "19:00"}])
    _enroll(db, student, a, b)
    assert resolve_default_class(db, student, now=_at(WED, "21:00")) is None


def test_a_regular_post_out_of_hours_counts_for_a_class(client, db, teacher, student,
                                                       auth_headers):
    # Neither class has a schedule, so the result cannot depend on when CI
    # runs: the newer class wins.
    a = _class(db, teacher, "A", [])
    b = _class(db, teacher, "B", [])
    _enroll(db, student, a, b)
    r = client.post("/api/posts", data={"content": "hola a todos"}, headers=auth_headers)
    assert r.status_code == 201, r.text
    assert r.json()["class_id"] == b.id
