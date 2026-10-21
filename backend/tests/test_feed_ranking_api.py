from datetime import timedelta

from app.models import Like, Post, utcnow


def _mk(db, author, klass, content, age_h=0, **kw):
    p = Post(author_id=author.id, content=content, class_id=klass.id,
             created_at=utcnow() - timedelta(hours=age_h),
             last_activity_at=utcnow() - timedelta(hours=age_h), **kw)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _ids(client, headers, url="/api/feed?limit=50"):
    return [p["id"] for p in client.get(url, headers=headers).json()["items"]]


def test_what_i_gave_aura_sinks_for_me(client, db, auth_headers, enrolled, klass, student, student2):
    a = _mk(db, student2, klass, "a", age_h=1)
    b = _mk(db, student2, klass, "b", age_h=2)
    assert _ids(client, auth_headers)[:2] == [a.id, b.id]
    db.add(Like(user_id=student.id, post_id=a.id))
    db.commit()
    assert _ids(client, auth_headers)[:2] == [b.id, a.id]


def test_it_does_not_sink_for_someone_else(client, db, auth_headers, student2_headers,
                                           enrolled, klass, student, student2, teacher):
    a = _mk(db, teacher, klass, "a", age_h=1)
    b = _mk(db, teacher, klass, "b", age_h=2)
    db.add(Like(user_id=student.id, post_id=a.id))
    db.commit()
    assert _ids(client, student2_headers)[:2] == [a.id, b.id]


def test_a_reply_to_my_post_brings_it_back(client, db, auth_headers, enrolled, klass, student, student2):
    mine = _mk(db, student, klass, "mine", age_h=48)
    fresh = _mk(db, student2, klass, "fresh", age_h=0)
    _mk(db, student2, klass, "answer", age_h=0, parent_id=mine.id)
    assert _ids(client, auth_headers)[:2] == [mine.id, fresh.id]


def test_old_posts_without_recent_replies_go_last_in_date_order(
        client, db, auth_headers, enrolled, klass, student, student2):
    old1 = _mk(db, student2, klass, "old1", age_h=24 * 20)
    old2 = _mk(db, student2, klass, "old2", age_h=24 * 30)
    new = _mk(db, student2, klass, "new", age_h=1)
    revived = _mk(db, student2, klass, "revived", age_h=24 * 40)
    _mk(db, student, klass, "r", age_h=1, parent_id=revived.id)
    ids = _ids(client, auth_headers)
    assert set(ids[:2]) == {new.id, revived.id}
    assert ids[2:] == [old1.id, old2.id]


def test_paging_is_stable_while_i_interact(client, db, auth_headers, enrolled, klass, student, student2):
    all_ids = {_mk(db, student2, klass, f"p{i}", age_h=i).id for i in range(25)}
    seen = []
    url = "/api/feed?limit=10"
    while url:
        body = client.get(url, headers=auth_headers).json()
        page = [p["id"] for p in body["items"]]
        seen += page
        # Between pages: aura on everything just seen, and a brand-new post.
        for pid in page:
            db.add(Like(user_id=student.id, post_id=pid))
        _mk(db, student2, klass, "late")
        url = f"/api/feed?limit=10&cursor={body['next_cursor']}" if body["next_cursor"] else None
    assert len(seen) == len(set(seen))
    assert set(seen) == all_ids


def test_vetoed_roots_stay_and_deleted_ones_do_not(client, db, auth_headers, enrolled, klass, student2):
    v = _mk(db, student2, klass, "v", status="vetoed")
    d = _mk(db, student2, klass, "d", status="deleted")
    ids = _ids(client, auth_headers)
    assert v.id in ids and d.id not in ids


def test_negative_offset_cursor_is_rejected(client, auth_headers):
    from app.services.cursor import encode_feed_cursor
    bad = encode_feed_cursor(utcnow(), -1)
    assert client.get(f"/api/feed?cursor={bad}", headers=auth_headers).status_code == 422


def test_entregas_do_not_lift_a_tarea(client, db, teacher_headers, klass, student, teacher, student2):
    # Replies under an assignment are homework, not conversation: an entrega
    # to the teacher's tarea must not pull it above a fresh post.
    tarea = _mk(db, teacher, klass, "tarea", age_h=48, type="tarea")
    _mk(db, student, klass, "mi entrega", age_h=0, parent_id=tarea.id, is_entrega=True)
    fresh = _mk(db, student2, klass, "fresh", age_h=0)
    ids = _ids(client, teacher_headers)
    assert ids.index(fresh.id) < ids.index(tarea.id)


def test_an_old_keyset_cursor_is_rejected(client, auth_headers):
    # A tab still running the previous bundle sends "<last_activity_at>|<post_id>";
    # it must not be read as {as_of, offset}.
    from app.services.cursor import encode_cursor
    old = encode_cursor(utcnow(), 37)
    assert client.get(f"/api/feed?cursor={old}", headers=auth_headers).status_code == 422
