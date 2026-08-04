from datetime import datetime, timedelta, timezone

from app.models import Post

NOW = datetime.now(timezone.utc)
SOON = NOW + timedelta(days=3)
LATER = NOW + timedelta(days=10)
PAST = NOW - timedelta(days=1)


def _tarea(db, teacher, klass, due):
    p = Post(author_id=teacher.id, class_id=klass.id, type="tarea",
             content=f"Tarea {due.date()}", due_date=due)
    db.add(p)
    db.commit()
    return p


def _pinned_ids(client, headers):
    return [p["id"] for p in client.get("/api/feed", headers=headers).json()["pinned"]]


def test_an_open_tarea_is_pinned(client, db, teacher, auth_headers, klass, enrolled):
    t = _tarea(db, teacher, klass, SOON)
    assert _pinned_ids(client, auth_headers) == [t.id]


def test_a_past_due_tarea_is_not_pinned(client, db, teacher, auth_headers, klass, enrolled):
    _tarea(db, teacher, klass, PAST)
    assert _pinned_ids(client, auth_headers) == []


def test_delivering_unpins_it_for_you(client, db, teacher, student, auth_headers, klass, enrolled):
    t = _tarea(db, teacher, klass, SOON)
    db.add(Post(author_id=student.id, class_id=klass.id, type="regular",
                parent_id=t.id, content="mi entrega", is_entrega=True))
    db.commit()
    assert _pinned_ids(client, auth_headers) == []


def test_it_stays_pinned_for_a_classmate_who_has_not_delivered(
    client, db, teacher, student, auth_headers, student2_headers, klass, enrolled
):
    t = _tarea(db, teacher, klass, SOON)
    db.add(Post(author_id=student.id, class_id=klass.id, type="regular",
                parent_id=t.id, content="mi entrega", is_entrega=True))
    db.commit()
    assert _pinned_ids(client, auth_headers) == []
    assert _pinned_ids(client, student2_headers) == [t.id]


def test_soonest_deadline_first(client, db, teacher, auth_headers, klass, enrolled):
    later = _tarea(db, teacher, klass, LATER)
    soon = _tarea(db, teacher, klass, SOON)
    assert _pinned_ids(client, auth_headers) == [soon.id, later.id]


def test_another_class_tarea_is_never_pinned(client, db, auth_headers, enrolled):
    from tests.test_feed_scoping import _other_class_with_tarea

    tarea, _ = _other_class_with_tarea(db)
    assert tarea.id not in _pinned_ids(client, auth_headers)


def test_pinned_is_identical_on_every_page(client, db, teacher, student, auth_headers, klass, enrolled):
    """It rides outside pagination on purpose — the same short list on every
    page, so no cursor can interact with it."""
    t = _tarea(db, teacher, klass, SOON)
    for i in range(25):
        db.add(Post(author_id=student.id, class_id=klass.id, content=f"p{i}"))
    db.commit()
    first = client.get("/api/feed?limit=20", headers=auth_headers).json()
    assert [p["id"] for p in first["pinned"]] == [t.id]
    second = client.get(
        f"/api/feed?limit=20&cursor={first['next_cursor']}", headers=auth_headers
    ).json()
    assert [p["id"] for p in second["pinned"]] == [t.id]
