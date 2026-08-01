from datetime import date

from app.models import AttendanceRecord, ClassSession, utcnow


def _open(client, headers, klass_id):
    return client.post(f"/api/classes/{klass_id}/sessions", headers=headers)


def _close(client, headers, klass_id, session_id):
    return client.delete(
        f"/api/classes/{klass_id}/sessions/{session_id}", headers=headers
    )


def _put(client, headers, session_id, records):
    return client.put(
        f"/api/sessions/{session_id}/attendance",
        json={"records": records},
        headers=headers,
    )


def test_teacher_opens_session(client, teacher_headers, klass):
    r = _open(client, teacher_headers, klass.id)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["class_id"] == klass.id
    assert body["closed_at"] is None
    assert body["opened_at"] is not None


def test_student_cannot_open_session(client, auth_headers, klass):
    r = _open(client, auth_headers, klass.id)
    assert r.status_code == 403


def test_duplicate_open_session_rejected(client, teacher_headers, klass):
    _open(client, teacher_headers, klass.id)
    r = _open(client, teacher_headers, klass.id)
    assert r.status_code == 409


def test_close_session(client, teacher_headers, klass):
    session_id = _open(client, teacher_headers, klass.id).json()["id"]
    r = _close(client, teacher_headers, klass.id, session_id)
    assert r.status_code == 204


def test_list_sessions_most_recent_first(client, db, teacher_headers, klass):
    s1 = ClassSession(class_id=klass.id, date=date(2026, 8, 17), opened_at=utcnow())
    s2 = ClassSession(class_id=klass.id, date=date(2026, 8, 18), opened_at=utcnow())
    db.add_all([s1, s2])
    db.commit()
    r = client.get(f"/api/classes/{klass.id}/sessions", headers=teacher_headers)
    assert r.status_code == 200
    dates = [s["date"] for s in r.json()["sessions"]]
    assert dates == sorted(dates, reverse=True)


def test_active_session_returns_open_session(client, teacher_headers, klass):
    session_id = _open(client, teacher_headers, klass.id).json()["id"]
    r = client.get(f"/api/classes/{klass.id}/sessions/active",
                   headers=teacher_headers)
    assert r.status_code == 200
    assert r.json()["id"] == session_id


def test_active_session_returns_null_when_closed(client, teacher_headers, klass):
    session_id = _open(client, teacher_headers, klass.id).json()["id"]
    _close(client, teacher_headers, klass.id, session_id)
    r = client.get(f"/api/classes/{klass.id}/sessions/active",
                   headers=teacher_headers)
    assert r.status_code == 200
    assert r.json() is None


def test_attendance_count_in_session_list(client, teacher_headers,
                                          klass, student, enrolled):
    session_id = _open(client, teacher_headers, klass.id).json()["id"]
    _put(client, teacher_headers, session_id,
         [{"user_id": student.id, "status": "absent"}])
    r = client.get(f"/api/classes/{klass.id}/sessions", headers=teacher_headers)
    session = next(s for s in r.json()["sessions"] if s["id"] == session_id)
    assert session["attendance_count"] == 1


def test_put_attendance_saves_records(client, teacher_headers, klass, student, enrolled):
    session_id = _open(client, teacher_headers, klass.id).json()["id"]
    r = _put(client, teacher_headers, session_id,
             [{"user_id": student.id, "status": "present"}])
    assert r.status_code == 200
    assert r.json()["saved"] == 1


def test_put_attendance_upserts_replaces_previous(client, db, teacher_headers,
                                                   klass, student, enrolled):
    session_id = _open(client, teacher_headers, klass.id).json()["id"]
    _put(client, teacher_headers, session_id,
         [{"user_id": student.id, "status": "present"}])
    _put(client, teacher_headers, session_id,
         [{"user_id": student.id, "status": "absent"}])
    records = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.session_id == session_id)
        .all()
    )
    assert len(records) == 1
    assert records[0].status == "absent"


def test_absent_record_appears_in_grade(client, teacher_headers,
                                        auth_headers, klass, student, enrolled):
    session_id = _open(client, teacher_headers, klass.id).json()["id"]
    _put(client, teacher_headers, session_id,
         [{"user_id": student.id, "status": "absent"}])
    grade = client.get(
        f"/api/students/me/grade?class_id={klass.id}", headers=auth_headers
    ).json()
    assert grade["faltas"]["count"] == 1
    assert grade["faltas"]["points"] == 10.0
    assert grade["total"] == -10.0


def test_late_does_not_count_as_falta(client, teacher_headers,
                                      auth_headers, klass, student, enrolled):
    session_id = _open(client, teacher_headers, klass.id).json()["id"]
    _put(client, teacher_headers, session_id,
         [{"user_id": student.id, "status": "late"}])
    grade = client.get(
        f"/api/students/me/grade?class_id={klass.id}", headers=auth_headers
    ).json()
    assert grade["faltas"]["count"] == 0
