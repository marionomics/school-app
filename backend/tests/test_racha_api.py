from datetime import datetime, timedelta, timezone

from app.models import Post


def _past(db, author, days_ago):
    db.add(Post(author_id=author.id, content="x" * 25,
                created_at=datetime.now(timezone.utc) - timedelta(days=days_ago)))
    db.commit()


def test_streak_me_while_today_is_open(client, db, student, enrolled, auth_headers):
    for d in (1, 2, 3):
        _past(db, student, d)
    r = client.get("/api/streak/me", headers=auth_headers).json()
    assert r["days"] == 3 and r["today_done"] is False
    assert r["level"]["from_days"] == 3 and r["next_level_at"] == 7
    assert r["odds"] == {"x2": 0.15, "x3": 0.0}
    assert len(r["levels"]) == 3


def test_streak_me_for_the_teacher_is_empty(client, teacher_headers):
    r = client.get("/api/streak/me", headers=teacher_headers).json()
    assert r["days"] == 0 and r["odds"] == {"x2": 0.0, "x3": 0.0}


def test_profile_shows_the_streak(client, db, student, enrolled, auth_headers):
    student.username = "alumno1"
    db.commit()
    _past(db, student, 0)
    assert client.get("/api/users/alumno1", headers=auth_headers).json()["streak_days"] == 1


def test_teacher_edits_the_levels(client, klass, teacher_headers):
    levels = [{"from_days": 2, "x2": 0.3, "x3": 0.1}]
    r = client.patch(f"/api/classes/{klass.id}/settings",
                     json={"streak_levels": levels}, headers=teacher_headers)
    assert r.status_code == 200, r.text
    assert r.json()["streak_levels"] == levels
    assert client.get(f"/api/classes/{klass.id}/settings",
                      headers=teacher_headers).json()["streak_levels"] == levels


def test_all_zero_levels_are_allowed(client, klass, teacher_headers):
    r = client.patch(f"/api/classes/{klass.id}/settings",
                     json={"streak_levels": [{"from_days": 1, "x2": 0, "x3": 0}]},
                     headers=teacher_headers)
    assert r.status_code == 200


def test_malformed_levels_are_rejected(client, klass, teacher_headers):
    bad = [
        [{"from_days": 7, "x2": 0.1, "x3": 0}, {"from_days": 3, "x2": 0.1, "x3": 0}],
        [{"from_days": 3, "x2": 0.1, "x3": 0}, {"from_days": 3, "x2": 0.2, "x3": 0}],
        [{"from_days": 3, "x2": 0.8, "x3": 0.3}],
        [{"from_days": 3, "x2": -0.1, "x3": 0}],
        [{"from_days": 0, "x2": 0.1, "x3": 0}],
        [{"from_days": i + 1, "x2": 0, "x3": 0} for i in range(9)],
    ]
    for levels in bad:
        r = client.patch(f"/api/classes/{klass.id}/settings",
                         json={"streak_levels": levels}, headers=teacher_headers)
        assert r.status_code == 422, levels
