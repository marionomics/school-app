from datetime import date

from app.models import AttendanceRecord, ClassSession, User


def _absent_on(db, klass, student, day, status="absent"):
    s = ClassSession(class_id=klass.id, date=day)
    db.add(s)
    db.flush()
    rec = AttendanceRecord(session_id=s.id, user_id=student.id, status=status)
    db.add(rec)
    db.commit()
    return s, rec


def _justify(client, headers, record_id, justified=True):
    return client.put(f"/api/attendance/{record_id}/justification",
                      json={"justified": justified}, headers=headers)


def _total(client, headers, klass):
    return client.get(f"/api/students/me/grade?class_id={klass.id}", headers=headers).json()


def test_justifying_a_falta_removes_the_ten_points_and_unjustifying_restores_them(
        client, db, teacher_headers, auth_headers, klass, student, enrolled):
    _, rec = _absent_on(db, klass, student, date(2026, 9, 7))
    assert _total(client, auth_headers, klass)["total"] == -10.0

    r = _justify(client, teacher_headers, rec.id)
    assert r.status_code == 200, r.text
    assert r.json() == {"record_id": rec.id, "justified": True}
    g = _total(client, auth_headers, klass)
    assert g["faltas"]["count"] == 0
    assert g["total"] == 0.0

    _justify(client, teacher_headers, rec.id, justified=False)
    assert _total(client, auth_headers, klass)["total"] == -10.0


def test_re_saving_pasar_lista_keeps_the_justification(
        client, db, teacher_headers, auth_headers, klass, student, enrolled):
    # PUT attendance used to delete every record and re-insert: saving the list
    # again silently wiped the justification and brought the −10 back.
    s, rec = _absent_on(db, klass, student, date(2026, 9, 7))
    _justify(client, teacher_headers, rec.id)
    for status in ("absent", "present", "absent"):
        r = client.put(f"/api/sessions/{s.id}/attendance",
                       json={"records": [{"user_id": student.id, "status": status}]},
                       headers=teacher_headers)
        assert r.status_code == 200
    assert _total(client, auth_headers, klass)["faltas"]["count"] == 0


def test_pasar_lista_still_drops_students_no_longer_listed(
        client, db, teacher_headers, klass, student, enrolled, student2):
    s, _ = _absent_on(db, klass, student, date(2026, 9, 7))
    client.put(f"/api/sessions/{s.id}/attendance",
               json={"records": [{"user_id": student2.id, "status": "present"}]},
               headers=teacher_headers)
    db.expire_all()
    users = {r.user_id for r in db.query(AttendanceRecord).filter_by(session_id=s.id)}
    assert users == {student2.id}


def test_only_an_absence_can_be_justified(client, db, teacher_headers, klass, student, enrolled):
    _, late = _absent_on(db, klass, student, date(2026, 9, 7), status="late")
    assert _justify(client, teacher_headers, late.id).status_code == 422


def test_only_the_classes_teacher_can_justify(client, db, teacher_headers, auth_headers,
                                              klass, student, enrolled):
    from app.auth.sessions import create_session

    _, rec = _absent_on(db, klass, student, date(2026, 9, 7))
    assert _justify(client, auth_headers, rec.id).status_code == 403
    other = User(google_id="g-other", email="otro@example.com", name="Otro", role="teacher")
    db.add(other)
    db.commit()
    headers = {"Authorization": f"Bearer {create_session(db, other)}"}
    assert _justify(client, headers, rec.id).status_code == 403
    assert _justify(client, teacher_headers, 99999).status_code == 404


def test_faltas_list_shows_every_absence_newest_first_with_its_state(
        client, db, teacher_headers, klass, student, enrolled):
    _, old = _absent_on(db, klass, student, date(2026, 9, 7))
    _, new = _absent_on(db, klass, student, date(2026, 9, 14))
    _absent_on(db, klass, student, date(2026, 9, 21), status="present")
    _justify(client, teacher_headers, old.id)
    r = client.get(f"/api/classes/{klass.id}/students/{student.id}/faltas",
                   headers=teacher_headers)
    assert r.status_code == 200, r.text
    assert r.json()["faltas"] == [
        {"record_id": new.id, "date": "2026-09-14", "justified": False},
        {"record_id": old.id, "date": "2026-09-07", "justified": True},
    ]
