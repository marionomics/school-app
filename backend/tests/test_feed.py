import time

from app.models import Post, utcnow


def _mk(db, author, klass, content, **kw):
    p = Post(author_id=author.id, content=content, class_id=klass.id, **kw)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_feed_orders_by_activity_and_paginates(client, db, auth_headers, enrolled, klass, student):
    ids = [_mk(db, student, klass, f"p{i}").id for i in range(5)]
    # bump the oldest post to the top
    oldest = db.get(Post, ids[0])
    oldest.last_activity_at = utcnow()
    db.commit()

    res = client.get("/api/feed?limit=3", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert [p["id"] for p in body["items"]][0] == ids[0]  # bumped first
    assert len(body["items"]) == 3
    assert body["next_cursor"] is not None

    res2 = client.get(f"/api/feed?limit=3&cursor={body['next_cursor']}", headers=auth_headers)
    ids2 = [p["id"] for p in res2.json()["items"]]
    assert set(ids2).isdisjoint({p["id"] for p in body["items"]})
    assert res2.json()["next_cursor"] is None


def test_feed_excludes_replies_and_removed(client, db, auth_headers, enrolled, klass, student):
    root = _mk(db, student, klass, "root")
    _mk(db, student, klass, "reply", parent_id=root.id)
    gone = _mk(db, student, klass, "bye", status="deleted")
    res = client.get("/api/feed", headers=auth_headers)
    ids = [p["id"] for p in res.json()["items"]]
    assert root.id in ids and gone.id not in ids
    assert all(p["parent_id"] is None for p in res.json()["items"])


def test_feed_bad_cursor(client, auth_headers):
    assert client.get("/api/feed?cursor=garbage!", headers=auth_headers).status_code == 422


def test_thread_view(client, db, auth_headers, enrolled, klass, student):
    root = _mk(db, student, klass, "root")
    r1 = _mk(db, student, klass, "nivel2", parent_id=root.id)
    _mk(db, student, klass, "nivel3", parent_id=r1.id)
    deleted = _mk(db, student, klass, "secreto", parent_id=root.id, status="deleted")
    res = client.get(f"/api/posts/{root.id}", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["post"]["id"] == root.id
    assert len(body["replies"]) == 3
    blanked = [r for r in body["replies"] if r["id"] == deleted.id][0]
    assert blanked["content"] == "" and blanked["status"] == "deleted"


def test_thread_404_for_removed_leaf(client, db, auth_headers, enrolled, klass, student):
    gone = _mk(db, student, klass, "x", status="deleted")
    assert client.get(f"/api/posts/{gone.id}", headers=auth_headers).status_code == 404
