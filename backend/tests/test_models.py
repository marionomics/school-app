from app.models import AuthSession, User


def test_user_defaults(db):
    user = User(google_id="g1", email="a@example.com", name="Alumno Uno")
    db.add(user)
    db.commit()
    db.refresh(user)
    assert user.role == "student"
    assert user.username is None
    assert user.bio == ""
    assert user.grade_is_private is False


def test_auth_session_links_user(db):
    user = User(google_id="g2", email="b@example.com", name="Alumno Dos")
    db.add(user)
    db.commit()
    session = AuthSession(user_id=user.id, token="tok123")
    db.add(session)
    db.commit()
    db.refresh(session)
    assert session.user.email == "b@example.com"
    assert session.expires_at is not None
