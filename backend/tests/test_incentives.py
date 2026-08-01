from app.models import Incentive, PointsLedger


def _create(client, headers, klass, name="Libreta", points=5):
    return client.post(
        f"/api/classes/{klass.id}/incentives",
        json={"name": name, "points": points, "description": "desc"},
        headers=headers,
    )


def test_teacher_creates_incentive(client, teacher_headers, klass):
    r = _create(client, teacher_headers, klass)
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "Libreta"
    assert float(r.json()["points"]) == 5.0
    assert r.json()["deleted_at"] is None


def test_student_cannot_create_incentive(client, auth_headers, klass, enrolled):
    r = _create(client, auth_headers, klass)
    assert r.status_code == 403


def test_list_incentives_excludes_deleted(client, teacher_headers, klass):
    r = _create(client, teacher_headers, klass, name="A")
    inc_id = r.json()["id"]
    del_r = client.delete(f"/api/incentives/{inc_id}", headers=teacher_headers)
    assert del_r.status_code == 204
    lst = client.get(f"/api/classes/{klass.id}/incentives", headers=teacher_headers)
    assert all(i["id"] != inc_id for i in lst.json()["incentives"])


def test_award_writes_ledger_row(client, db, teacher_headers, klass, student, enrolled):
    inc_id = _create(client, teacher_headers, klass, points=10).json()["id"]
    r = client.post(
        f"/api/incentives/{inc_id}/award",
        json={"student_id": student.id},
        headers=teacher_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["source_type"] == "incentive"
    assert float(r.json()["points"]) == 10.0
    rows = db.query(PointsLedger).filter(
        PointsLedger.source_type == "incentive",
        PointsLedger.user_id == student.id,
    ).all()
    assert len(rows) == 1


def test_teacher_can_award_same_incentive_multiple_times(
    client, db, teacher_headers, klass, student, enrolled
):
    inc_id = _create(client, teacher_headers, klass, points=5).json()["id"]
    client.post(
        f"/api/incentives/{inc_id}/award",
        json={"student_id": student.id},
        headers=teacher_headers,
    )
    client.post(
        f"/api/incentives/{inc_id}/award",
        json={"student_id": student.id},
        headers=teacher_headers,
    )
    rows = db.query(PointsLedger).filter(
        PointsLedger.source_type == "incentive",
        PointsLedger.user_id == student.id,
    ).all()
    assert len(rows) == 2


def test_award_unenrolled_student_is_rejected(
    client, teacher_headers, klass, student
):
    inc_id = _create(client, teacher_headers, klass, points=5).json()["id"]
    r = client.post(
        f"/api/incentives/{inc_id}/award",
        json={"student_id": student.id},
        headers=teacher_headers,
    )
    assert r.status_code == 422


def test_incentive_points_appear_in_grade_breakdown(
    client, teacher_headers, auth_headers, klass, student, enrolled
):
    inc_id = _create(client, teacher_headers, klass, points=7).json()["id"]
    client.post(
        f"/api/incentives/{inc_id}/award",
        json={"student_id": student.id},
        headers=teacher_headers,
    )
    grade = client.get(
        f"/api/students/me/grade?class_id={klass.id}", headers=auth_headers
    ).json()
    assert grade["ledger"]["other"] == 7.0


def test_soft_delete_when_incentive_has_been_awarded(
    client, db, teacher_headers, klass, student, enrolled
):
    inc_id = _create(client, teacher_headers, klass, points=3).json()["id"]
    client.post(
        f"/api/incentives/{inc_id}/award",
        json={"student_id": student.id},
        headers=teacher_headers,
    )
    r = client.delete(f"/api/incentives/{inc_id}", headers=teacher_headers)
    assert r.status_code == 204
    inc = db.get(Incentive, inc_id)
    assert inc is not None
    assert inc.deleted_at is not None


def test_hard_delete_when_incentive_never_awarded(
    client, db, teacher_headers, klass
):
    inc_id = _create(client, teacher_headers, klass, points=3).json()["id"]
    r = client.delete(f"/api/incentives/{inc_id}", headers=teacher_headers)
    assert r.status_code == 204
    assert db.get(Incentive, inc_id) is None


def test_student_cannot_award(
    client, auth_headers, klass, enrolled, teacher, db
):
    from app.auth.sessions import create_session

    inc_id = _create(
        client,
        {"Authorization": f"Bearer {create_session(db, teacher)}"},
        klass,
    ).json()["id"]
    r = client.post(
        f"/api/incentives/{inc_id}/award",
        json={"student_id": 1},
        headers=auth_headers,
    )
    assert r.status_code == 403
