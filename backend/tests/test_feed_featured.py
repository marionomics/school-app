from datetime import timedelta

from app.models import Like, Post, utcnow


def _mk(db, author, klass, content, age_h=0, **kw):
    p = Post(author_id=author.id, content=content, class_id=klass.id,
             created_at=utcnow() - timedelta(hours=age_h), **kw)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _item(client, headers, pid):
    items = client.get("/api/feed?limit=50", headers=headers).json()["items"]
    return next(p for p in items if p["id"] == pid)


def test_no_replies_no_featured(client, db, auth_headers, enrolled, klass, student):
    root = _mk(db, student, klass, "root")
    assert _item(client, auth_headers, root.id)["featured_reply"] is None


def test_the_teacher_aura_reply_is_featured(client, db, auth_headers, enrolled, klass,
                                            student, student2, teacher):
    root = _mk(db, student, klass, "root")
    popular = _mk(db, student2, klass, "popular", parent_id=root.id, like_count=5)
    blessed = _mk(db, student2, klass, "blessed", parent_id=root.id, age_h=2)
    db.add(Like(user_id=teacher.id, post_id=blessed.id))
    db.commit()
    fr = _item(client, auth_headers, root.id)["featured_reply"]
    assert fr["id"] == blessed.id
    assert fr["teacher_aura"] is True
    assert fr["author"]["id"] == student2.id
    assert popular.id != fr["id"]


def test_most_aura_then_most_recent(client, db, auth_headers, enrolled, klass, student, student2):
    root = _mk(db, student, klass, "root")
    _mk(db, student2, klass, "older", parent_id=root.id, age_h=3, like_count=2)
    newer = _mk(db, student2, klass, "newer", parent_id=root.id, age_h=1, like_count=2)
    assert _item(client, auth_headers, root.id)["featured_reply"]["id"] == newer.id


def test_level3_and_inactive_replies_are_never_featured(client, db, auth_headers, enrolled,
                                                        klass, student, student2):
    root = _mk(db, student, klass, "root")
    l2 = _mk(db, student2, klass, "l2", parent_id=root.id, status="deleted")
    _mk(db, student2, klass, "l3", parent_id=l2.id, like_count=9)
    _mk(db, student2, klass, "vetoed", parent_id=root.id, status="vetoed", like_count=9)
    assert _item(client, auth_headers, root.id)["featured_reply"] is None


def test_never_under_a_tarea(client, db, auth_headers, enrolled, klass, student, teacher):
    tarea = _mk(db, teacher, klass, "tarea", type="tarea")
    _mk(db, student, klass, "mi respuesta", parent_id=tarea.id, like_count=3)
    assert _item(client, auth_headers, tarea.id)["featured_reply"] is None


def test_never_under_an_examen(client, db, auth_headers, enrolled, klass, student, teacher):
    examen = _mk(db, teacher, klass, "examen", type="examen")
    _mk(db, student, klass, "mi respuesta", parent_id=examen.id)
    assert _item(client, auth_headers, examen.id)["featured_reply"] is None


def test_the_thread_endpoint_carries_no_featured_reply(client, db, auth_headers, enrolled,
                                                       klass, student, student2):
    root = _mk(db, student, klass, "root")
    _mk(db, student2, klass, "r", parent_id=root.id)
    body = client.get(f"/api/posts/{root.id}", headers=auth_headers).json()
    assert body["post"]["featured_reply"] is None
