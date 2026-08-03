from datetime import date, datetime, timezone

from app.auth.sessions import create_session
from app.models import Class, Post, User

SOON = datetime(2026, 12, 1, tzinfo=timezone.utc)


def _other_class_with_tarea(db):
    t = User(google_id="g-t2", email="t2@example.com", name="Profe2", role="teacher")
    db.add(t)
    db.commit()
    k = Class(name="Otra", code="OTRA2026Z", teacher_id=t.id,
              start_date=date(2026, 8, 17), end_date=date(2026, 12, 4),
              schedule_json=[])
    db.add(k)
    db.commit()
    tarea = Post(author_id=t.id, class_id=k.id, type="tarea",
                 content="Tarea de otra clase", due_date=SOON)
    regular = Post(author_id=t.id, class_id=k.id, type="regular",
                   content="Post normal de otra clase")
    db.add_all([tarea, regular])
    db.commit()
    return tarea, regular


def _feed_ids(client, headers):
    return [p["id"] for p in client.get("/api/feed", headers=headers).json()["items"]]


def test_a_tarea_from_another_class_is_not_in_your_feed(client, db, auth_headers, enrolled):
    """A student confidently mistaking another class's homework for their own
    is the harm this prevents."""
    tarea, _ = _other_class_with_tarea(db)
    assert tarea.id not in _feed_ids(client, auth_headers)


def test_a_regular_post_from_another_class_still_is(client, db, auth_headers, enrolled):
    """The feed stays global for social content — that is the product."""
    _, regular = _other_class_with_tarea(db)
    assert regular.id in _feed_ids(client, auth_headers)


def test_your_own_class_tarea_is_in_your_feed(client, db, teacher, auth_headers, klass, enrolled):
    tarea = Post(author_id=teacher.id, class_id=klass.id, type="tarea",
                 content="Mi tarea", due_date=SOON)
    db.add(tarea)
    db.commit()
    assert tarea.id in _feed_ids(client, auth_headers)


def test_the_teacher_sees_their_own_class_tarea(client, db, teacher, teacher_headers, klass):
    tarea = Post(author_id=teacher.id, class_id=klass.id, type="tarea",
                 content="Mi tarea", due_date=SOON)
    db.add(tarea)
    db.commit()
    assert tarea.id in _feed_ids(client, teacher_headers)


def test_a_ghost_still_sees_their_class_tarea(client, db, teacher, ghost, klass):
    """Ghost and polizón are legitimately in the class; they earn no points but
    the class's work is still theirs to read."""
    tarea = Post(author_id=teacher.id, class_id=klass.id, type="tarea",
                 content="Mi tarea", due_date=SOON)
    db.add(tarea)
    db.commit()
    headers = {"Authorization": f"Bearer {create_session(db, ghost)}"}
    assert tarea.id in _feed_ids(client, headers)


def test_an_examen_from_another_class_is_also_hidden(client, db, auth_headers, enrolled):
    t = User(google_id="g-t3", email="t3@example.com", name="Profe3", role="teacher")
    db.add(t)
    db.commit()
    k = Class(name="Tercera", code="TRES2026Z", teacher_id=t.id,
              start_date=date(2026, 8, 17), end_date=date(2026, 12, 4),
              schedule_json=[])
    db.add(k)
    db.commit()
    examen = Post(author_id=t.id, class_id=k.id, type="examen",
                  content="Parcial de otra clase", examen_mode="paper")
    db.add(examen)
    db.commit()
    assert examen.id not in _feed_ids(client, auth_headers)
