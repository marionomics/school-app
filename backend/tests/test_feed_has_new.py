from datetime import date
from urllib.parse import quote

from app.models import Class, Post


def _since(client, headers):
    return client.get("/api/feed", headers=headers).json()["as_of"]


def _has_new(client, headers, since):
    res = client.get(f"/api/feed/has-new?since={quote(since)}", headers=headers)
    assert res.status_code == 200
    return res.json()["has_new"]


def _post(db, author, klass, **kw):
    p = Post(author_id=author.id, class_id=klass.id, content="x", **kw)
    db.add(p)
    db.commit()
    return p


def test_nothing_new_right_after_loading(client, auth_headers, enrolled):
    since = _since(client, auth_headers)
    assert _has_new(client, auth_headers, since) is False


def test_someone_elses_post_is_new(client, db, auth_headers, enrolled, klass, student2):
    since = _since(client, auth_headers)
    _post(db, student2, klass)
    assert _has_new(client, auth_headers, since) is True


def test_my_own_post_is_not_new(client, db, auth_headers, enrolled, klass, student):
    since = _since(client, auth_headers)
    _post(db, student, klass)
    assert _has_new(client, auth_headers, since) is False


def test_another_class_tarea_is_not_new(client, db, auth_headers, enrolled, teacher):
    other = Class(name="Otra", code="OTRA2026TEST", teacher_id=teacher.id,
                  start_date=date(2026, 8, 17), end_date=date(2026, 12, 4), schedule_json=[])
    db.add(other)
    db.commit()
    since = _since(client, auth_headers)
    _post(db, teacher, other, type="tarea")
    assert _has_new(client, auth_headers, since) is False


def test_a_reply_in_my_thread_is_new(client, db, auth_headers, enrolled, klass, student, student2):
    root = _post(db, student2, klass)
    _post(db, student, klass, parent_id=root.id)
    since = _since(client, auth_headers)
    _post(db, student2, klass, parent_id=root.id)
    assert _has_new(client, auth_headers, since) is True


def test_a_reply_to_my_comment_at_level3_is_new(client, db, auth_headers, enrolled, klass,
                                                student, student2):
    root = _post(db, student2, klass)
    mine = _post(db, student, klass, parent_id=root.id)
    since = _since(client, auth_headers)
    _post(db, student2, klass, parent_id=mine.id)
    assert _has_new(client, auth_headers, since) is True


def test_a_reply_in_an_unrelated_thread_is_not_new(client, db, auth_headers, enrolled, klass,
                                                   student2, teacher):
    root = _post(db, teacher, klass)
    since = _since(client, auth_headers)
    _post(db, student2, klass, parent_id=root.id)
    assert _has_new(client, auth_headers, since) is False


def test_naive_or_garbage_since_is_rejected(client, auth_headers):
    assert client.get("/api/feed/has-new?since=2026-10-21T10:00:00",
                      headers=auth_headers).status_code == 422
    assert client.get("/api/feed/has-new?since=ayer", headers=auth_headers).status_code == 422


def test_an_entrega_does_not_light_the_pill(client, db, teacher_headers, klass, teacher, student, enrolled):
    tarea = _post(db, teacher, klass, type="tarea")
    since = _since(client, teacher_headers)
    _post(db, student, klass, parent_id=tarea.id, is_entrega=True)
    assert _has_new(client, teacher_headers, since) is False
