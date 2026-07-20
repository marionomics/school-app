from app import models
from app.routers import auth as auth_router


def fake_verify(credential: str) -> dict:
    if credential == "bad":
        raise ValueError("invalid")
    return {
        "sub": "google-sub-1",
        "email": "nuevo@example.com",
        "name": "Nuevo Alumno",
        "picture": "https://example.com/p.jpg",
    }


def test_google_login_creates_user(client, db, monkeypatch):
    monkeypatch.setattr(auth_router, "verify_google_token", fake_verify)
    res = client.post("/api/auth/google", json={"credential": "good"})
    assert res.status_code == 200
    body = res.json()
    assert body["needs_onboarding"] is True
    assert body["user"]["email"] == "nuevo@example.com"
    assert body["user"]["role"] == "student"
    assert body["token"]
    assert db.query(models.User).count() == 1


def test_google_login_teacher_email(client, db, monkeypatch):
    monkeypatch.setattr(auth_router, "verify_google_token", fake_verify)
    monkeypatch.setattr(auth_router.settings, "teacher_email", "nuevo@example.com")
    res = client.post("/api/auth/google", json={"credential": "good"})
    assert res.json()["user"]["role"] == "teacher"


def test_google_login_invalid_token(client, monkeypatch):
    monkeypatch.setattr(auth_router, "verify_google_token", fake_verify)
    res = client.post("/api/auth/google", json={"credential": "bad"})
    assert res.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_user(client, auth_headers):
    res = client.get("/api/auth/me", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["email"] == "alumno@example.com"


def test_logout_revokes_session(client, auth_headers):
    assert client.post("/api/auth/logout", headers=auth_headers).status_code == 204
    assert client.get("/api/auth/me", headers=auth_headers).status_code == 401


def test_config_is_public(client):
    res = client.get("/api/config")
    assert res.status_code == 200
    assert "google_client_id" in res.json()
