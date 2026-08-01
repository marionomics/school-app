def test_teacher_reads_settings(client, teacher_headers, klass):
    r = client.get(f"/api/classes/{klass.id}/settings", headers=teacher_headers)
    assert r.status_code == 200, r.text
    assert r.json()["tareas_weight"] == 30
    assert r.json()["examenes_weight"] == 30
    assert float(r.json()["tap_value"]) == 1.0
    assert float(r.json()["like_value"]) == 1.0
    assert float(r.json()["like_exponent"]) == 0.5


def test_teacher_updates_weights(client, db, teacher_headers, klass):
    r = client.patch(
        f"/api/classes/{klass.id}/settings",
        json={"tareas_weight": 40, "examenes_weight": 20},
        headers=teacher_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["tareas_weight"] == 40
    assert r.json()["examenes_weight"] == 20
    db.expire_all()
    from app.models import Class
    klass_db = db.get(Class, klass.id)
    assert klass_db.tareas_weight == 40


def test_teacher_updates_tap_value(client, teacher_headers, klass):
    r = client.patch(
        f"/api/classes/{klass.id}/settings",
        json={"tap_value": 2.0},
        headers=teacher_headers,
    )
    assert r.status_code == 200
    assert float(r.json()["tap_value"]) == 2.0


def test_patch_is_partial_other_fields_unchanged(client, teacher_headers, klass):
    client.patch(
        f"/api/classes/{klass.id}/settings",
        json={"tareas_weight": 25},
        headers=teacher_headers,
    )
    r = client.get(f"/api/classes/{klass.id}/settings", headers=teacher_headers)
    assert r.json()["examenes_weight"] == 30


def test_weight_above_100_is_rejected(client, teacher_headers, klass):
    r = client.patch(
        f"/api/classes/{klass.id}/settings",
        json={"tareas_weight": 101},
        headers=teacher_headers,
    )
    assert r.status_code == 422


def test_negative_weight_is_rejected(client, teacher_headers, klass):
    r = client.patch(
        f"/api/classes/{klass.id}/settings",
        json={"examenes_weight": -1},
        headers=teacher_headers,
    )
    assert r.status_code == 422


def test_zero_tap_value_is_rejected(client, teacher_headers, klass):
    r = client.patch(
        f"/api/classes/{klass.id}/settings",
        json={"tap_value": 0},
        headers=teacher_headers,
    )
    assert r.status_code == 422


def test_like_exponent_below_01_is_rejected(client, teacher_headers, klass):
    r = client.patch(
        f"/api/classes/{klass.id}/settings",
        json={"like_exponent": 0.05},
        headers=teacher_headers,
    )
    assert r.status_code == 422


def test_like_exponent_above_2_is_rejected(client, teacher_headers, klass):
    r = client.patch(
        f"/api/classes/{klass.id}/settings",
        json={"like_exponent": 2.1},
        headers=teacher_headers,
    )
    assert r.status_code == 422


def test_like_cap_is_not_accepted(client, teacher_headers, klass):
    r = client.patch(
        f"/api/classes/{klass.id}/settings",
        json={"like_cap": 10},
        headers=teacher_headers,
    )
    assert r.status_code == 422


def test_student_cannot_update_settings(client, auth_headers, klass, enrolled):
    r = client.patch(
        f"/api/classes/{klass.id}/settings",
        json={"tareas_weight": 10},
        headers=auth_headers,
    )
    assert r.status_code == 403


def test_other_teacher_cannot_update_settings(client, db, klass):
    from app.auth.sessions import create_session
    from app.models import User

    other = User(
        google_id="g-other2",
        email="otro2@example.com",
        name="Otro",
        role="teacher",
    )
    db.add(other)
    db.commit()
    headers = {"Authorization": f"Bearer {create_session(db, other)}"}
    r = client.patch(
        f"/api/classes/{klass.id}/settings",
        json={"tareas_weight": 10},
        headers=headers,
    )
    assert r.status_code == 403
