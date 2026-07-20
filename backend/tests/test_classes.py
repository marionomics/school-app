CLASS_PAYLOAD = {
    "name": "Microeconomía",
    "code_prefix": "MICRO",
    "start_date": "2026-08-17",
    "end_date": "2026-12-04",
    "schedule": [{"day": 0, "start": "10:00", "end": "11:00"}],
}


def test_create_requires_teacher(client, auth_headers):
    res = client.post("/api/classes", json=CLASS_PAYLOAD, headers=auth_headers)
    assert res.status_code == 403


def test_create_class(client, teacher_headers):
    res = client.post("/api/classes", json=CLASS_PAYLOAD, headers=teacher_headers)
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Microeconomía"
    assert body["code"].startswith("MICRO")
    assert body["tareas_weight"] == 30
    assert body["schedule"] == CLASS_PAYLOAD["schedule"]


def test_schedule_validation(client, teacher_headers):
    bad = dict(CLASS_PAYLOAD, schedule=[{"day": 9, "start": "10:00", "end": "11:00"}])
    assert client.post("/api/classes", json=bad, headers=teacher_headers).status_code == 422
    bad = dict(CLASS_PAYLOAD, schedule=[{"day": 0, "start": "25:00", "end": "11:00"}])
    assert client.post("/api/classes", json=bad, headers=teacher_headers).status_code == 422


def test_join_and_mine(client, auth_headers, teacher_headers):
    code = client.post("/api/classes", json=CLASS_PAYLOAD, headers=teacher_headers).json()["code"]

    res = client.post("/api/classes/join", json={"code": code}, headers=auth_headers)
    assert res.status_code == 200

    res = client.post("/api/classes/join", json={"code": code}, headers=auth_headers)
    assert res.status_code == 409

    res = client.post("/api/classes/join", json={"code": "NOPE2026XXXX"}, headers=auth_headers)
    assert res.status_code == 404

    mine = client.get("/api/classes/mine", headers=auth_headers).json()
    assert len(mine["enrolled"]) == 1 and mine["teaching"] == []

    mine = client.get("/api/classes/mine", headers=teacher_headers).json()
    assert len(mine["teaching"]) == 1


def test_detail_membership(client, db, auth_headers, teacher_headers):
    created = client.post("/api/classes", json=CLASS_PAYLOAD, headers=teacher_headers).json()
    client.post("/api/classes/join", json={"code": created["code"]}, headers=auth_headers)

    res = client.get(f"/api/classes/{created['id']}", headers=auth_headers)
    assert res.status_code == 200
    assert len(res.json()["members"]) == 1

    from app.auth.sessions import create_session
    from app.models import User

    outsider = User(google_id="g-out", email="out@example.com", name="Out")
    db.add(outsider)
    db.commit()
    headers = {"Authorization": f"Bearer {create_session(db, outsider)}"}
    assert client.get(f"/api/classes/{created['id']}", headers=headers).status_code == 403
