from app.models import User


def test_set_username_and_bio(client, auth_headers):
    res = client.patch(
        "/api/users/me",
        json={"username": "alumno_uno", "bio": "Economista en formación"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["username"] == "alumno_uno"
    assert res.json()["bio"] == "Economista en formación"


def test_username_format_rejected(client, auth_headers):
    for bad in ["Ab", "with spaces", "ñoño", "a" * 21, "UPPER"]:
        res = client.patch("/api/users/me", json={"username": bad}, headers=auth_headers)
        assert res.status_code == 422, bad


def test_username_taken(client, db, auth_headers):
    other = User(google_id="g-x", email="x@example.com", name="X", username="tomado")
    db.add(other)
    db.commit()
    res = client.patch("/api/users/me", json={"username": "tomado"}, headers=auth_headers)
    assert res.status_code == 409


def test_username_available(client, db, auth_headers):
    other = User(google_id="g-y", email="y@example.com", name="Y", username="ocupado")
    db.add(other)
    db.commit()
    res = client.get("/api/users/username-available?u=ocupado", headers=auth_headers)
    assert res.json() == {"available": False}
    res = client.get("/api/users/username-available?u=libre", headers=auth_headers)
    assert res.json() == {"available": True}
