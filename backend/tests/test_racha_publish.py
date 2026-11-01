from datetime import datetime, timedelta, timezone

import pytest

from app.auth.sessions import create_session
from app.models import Enrollment, Post, PostRoll, User
from app.services import streak


def _h(db, u):
    return {"Authorization": f"Bearer {create_session(db, u)}"}


def _past(db, author, days_ago):
    at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    db.add(Post(author_id=author.id, content="x" * 25, created_at=at))
    db.commit()


@pytest.fixture()
def draw(monkeypatch):
    box = {"u": 0.99}
    monkeypatch.setattr(streak, "_draw", lambda: box["u"])
    return box


def _publish(client, db, u, content="una publicación de más de veinte letras"):
    r = client.post("/api/posts", data={"content": content}, headers=_h(db, u))
    assert r.status_code == 201, r.text
    return r.json()


def test_every_qualifying_post_is_rolled_once_and_stored(client, db, student, enrolled, draw):
    body = _publish(client, db, student)
    rolls = db.query(PostRoll).all()
    assert len(rolls) == 1 and rolls[0].post_id == body["id"]
    assert rolls[0].multiplier == 1 and rolls[0].streak_days == 1
    assert body["multiplier"] is None


def test_a_seven_day_streak_can_roll_triple(client, db, student, enrolled, draw):
    for d in range(1, 7):
        _past(db, student, d)
    draw["u"] = 0.01                       # < x3 = 0.05 at 7 days
    body = _publish(client, db, student)
    assert body["multiplier"] == 3
    r = db.query(PostRoll).filter(PostRoll.post_id == body["id"]).one()
    assert r.streak_days == 7 and float(r.x3) == 0.05


def test_no_roll_for_short_or_teacher(client, db, student, enrolled, teacher, klass, draw):
    _publish(client, db, student, content="corto pero vale")    # < 20 chars
    _publish(client, db, teacher)
    assert db.query(PostRoll).count() == 0


def test_an_all_zero_class_stores_one_x_rolls(client, db, student, enrolled, klass, draw):
    from app.services.grades import get_config
    cfg = get_config(db, klass.id)
    cfg.streak_levels = [{"from_days": 1, "x2": 0, "x3": 0}]
    db.add(cfg)
    db.commit()
    draw["u"] = 0.0
    body = _publish(client, db, student)
    assert body["multiplier"] is None
    assert db.query(PostRoll).one().multiplier == 1


def test_a_stored_roll_never_changes_when_history_changes(client, db, student, enrolled, draw):
    for d in range(1, 7):
        _past(db, student, d)
    body = _publish(client, db, student)
    db.query(Post).filter(Post.id != body["id"]).update({"status": "deleted"})
    db.commit()
    assert db.query(PostRoll).one().streak_days == 7


def test_an_attachment_only_post_is_rolled(client, db, student, enrolled, draw, monkeypatch):
    from app import storage
    monkeypatch.setattr(storage, "is_r2_configured", lambda: True)
    monkeypatch.setattr(storage, "upload_bytes", lambda data, key, content_type: None)
    monkeypatch.setattr(storage, "generate_presigned_url",
                        lambda key, expires=3600: f"https://r2.test/{key}")
    r = client.post("/api/posts", data={"content": ""},
                    files=[("files", ("nota.pdf", b"%PDF-1.4", "application/pdf"))],
                    headers=_h(db, student))
    assert r.status_code == 201, r.text
    roll = db.query(PostRoll).filter(PostRoll.post_id == r.json()["id"]).one()
    assert roll.streak_days == 1
