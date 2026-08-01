from decimal import Decimal

from app.models import AttendanceRecord, ClassSession, PointsLedger, utcnow


def test_roster_requires_teacher(client, auth_headers, klass):
    r = client.get(f"/api/classes/{klass.id}/roster", headers=auth_headers)
    assert r.status_code == 403


def test_roster_returns_all_enrollments(client, teacher_headers, klass,
                                        student, enrolled, ghost):
    r = client.get(f"/api/classes/{klass.id}/roster", headers=teacher_headers)
    assert r.status_code == 200, r.text
    ids = {s["id"] for s in r.json()["students"]}
    assert student.id in ids
    assert ghost.id in ids


def test_roster_shows_ghost_status(client, teacher_headers, klass, ghost):
    r = client.get(f"/api/classes/{klass.id}/roster", headers=teacher_headers)
    row = next(s for s in r.json()["students"] if s["id"] == ghost.id)
    assert row["status"] == "ghost"


def test_roster_grade_reflects_falta(client, db, teacher_headers, klass,
                                      student, enrolled):
    session = ClassSession(class_id=klass.id, date=utcnow().date(),
                           opened_at=utcnow())
    db.add(session)
    db.flush()
    db.add(AttendanceRecord(session_id=session.id, user_id=student.id,
                            status="absent"))
    db.commit()
    r = client.get(f"/api/classes/{klass.id}/roster", headers=teacher_headers)
    row = next(s for s in r.json()["students"] if s["id"] == student.id)
    assert row["faltas"] == 1
    assert row["grade"] == -10.0


def test_roster_grade_reflects_points(client, db, teacher_headers, klass,
                                       student, enrolled):
    db.add(PointsLedger(user_id=student.id, class_id=klass.id,
                        source_type="participacion", source_id=1,
                        points=Decimal("5.00")))
    db.commit()
    r = client.get(f"/api/classes/{klass.id}/roster", headers=teacher_headers)
    row = next(s for s in r.json()["students"] if s["id"] == student.id)
    assert row["grade"] == 5.0


def test_teacher_can_view_student_grade(client, teacher_headers, klass,
                                        student, enrolled):
    r = client.get(
        f"/api/classes/{klass.id}/students/{student.id}/grade",
        headers=teacher_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["class_id"] == klass.id
    assert "total" in body
    assert "faltas" in body


def test_teacher_grade_view_requires_teacher(client, auth_headers, klass,
                                              student, enrolled):
    r = client.get(
        f"/api/classes/{klass.id}/students/{student.id}/grade",
        headers=auth_headers,
    )
    assert r.status_code == 403


def test_teacher_grade_view_404_if_not_enrolled(client, teacher_headers,
                                                 klass, student):
    r = client.get(
        f"/api/classes/{klass.id}/students/{student.id}/grade",
        headers=teacher_headers,
    )
    assert r.status_code == 404
