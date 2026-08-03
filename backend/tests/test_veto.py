from decimal import Decimal

from app.models import PointsLedger, Post


def _participacion(client, headers):
    return client.post("/api/posts", data={
        "content": "Expliqué el modelo de oferta y demanda", "type": "participacion",
        "taps": "3",
    }, headers=headers)


def _active_points(db, user_id) -> Decimal:
    rows = db.query(PointsLedger).filter(PointsLedger.user_id == user_id,
                                         PointsLedger.revoked_at.is_(None)).all()
    return sum((r.points for r in rows), Decimal("0"))


def test_veto_revokes_the_participacion_points(client, db, teacher_headers, auth_headers, student, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    assert _active_points(db, student.id) == Decimal("3.0")
    r = client.post(f"/api/posts/{pid}/veto", json={"reason": "no fue en clase"},
                    headers=teacher_headers)
    assert r.status_code == 200
    db.expire_all()
    assert _active_points(db, student.id) == Decimal("0")
    assert db.get(Post, pid).status == "vetoed"
    assert db.get(Post, pid).veto_reason == "no fue en clase"


def test_unveto_restores_them(client, db, teacher_headers, auth_headers, student, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    client.post(f"/api/posts/{pid}/veto", headers=teacher_headers)
    r = client.delete(f"/api/posts/{pid}/veto", headers=teacher_headers)
    assert r.status_code == 200
    db.expire_all()
    assert _active_points(db, student.id) == Decimal("3.0")
    assert db.get(Post, pid).status == "active"
    assert db.get(Post, pid).veto_reason is None


def test_veto_revokes_the_likes_too(client, db, teacher_headers, auth_headers, student2_headers, student, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    client.post(f"/api/posts/{pid}/like", headers=student2_headers)
    assert _active_points(db, student.id) == Decimal("4.0")     # 3 taps + 1 like
    client.post(f"/api/posts/{pid}/veto", headers=teacher_headers)
    db.expire_all()
    assert _active_points(db, student.id) == Decimal("0")       # no evidence, no points


def test_deleting_your_own_post_revokes_the_points(client, db, auth_headers, student, enrolled):
    """Deleting is not a way to bank points twice: award() dedupes on source_id,
    so a repost would earn again on a fresh source."""
    pid = _participacion(client, auth_headers).json()["id"]
    client.delete(f"/api/posts/{pid}", headers=auth_headers)
    db.expire_all()
    assert db.get(Post, pid).status == "deleted"
    assert _active_points(db, student.id) == Decimal("0")


def test_student_cannot_veto(client, auth_headers, student2_headers, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    r = client.post(f"/api/posts/{pid}/veto", headers=student2_headers)
    assert r.status_code == 403


def _feed_ids(client, headers):
    return [p["id"] for p in client.get("/api/feed", headers=headers).json()["items"]]


def test_a_vetoed_post_stays_in_the_feed(
    client, db, teacher_headers, auth_headers, student2_headers, enrolled
):
    pid = _participacion(client, auth_headers).json()["id"]
    client.post(
        f"/api/posts/{pid}/veto",
        json={"reason": "no fue en clase"},
        headers=teacher_headers,
    )
    assert pid in _feed_ids(client, auth_headers)  # its author sees it
    assert pid in _feed_ids(client, student2_headers)  # so does everyone else


def test_a_deleted_post_stays_out_of_the_feed(client, db, auth_headers, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    client.delete(f"/api/posts/{pid}", headers=auth_headers)
    assert pid not in _feed_ids(client, auth_headers)


def test_the_veto_reason_in_the_feed_is_still_private(
    client, db, teacher_headers, auth_headers, student2_headers, enrolled
):
    pid = _participacion(client, auth_headers).json()["id"]
    client.post(
        f"/api/posts/{pid}/veto",
        json={"reason": "no fue en clase"},
        headers=teacher_headers,
    )

    def reason_for(headers):
        items = client.get("/api/feed", headers=headers).json()["items"]
        return next(p for p in items if p["id"] == pid)["veto_reason"]

    assert reason_for(auth_headers) == "no fue en clase"
    assert reason_for(student2_headers) is None


def test_a_vetoed_post_keeps_its_text(client, db, teacher_headers, auth_headers, enrolled):
    """A veto removes the points, not the student's words. Blanking the text
    leaves an empty card in the feed with nothing to explain it."""
    pid = _participacion(client, auth_headers).json()["id"]
    client.post(f"/api/posts/{pid}/veto", headers=teacher_headers)
    body = client.get(f"/api/posts/{pid}", headers=auth_headers).json()["post"]
    assert body["content"] == "Expliqué el modelo de oferta y demanda"
    assert body["status"] == "vetoed"


def test_a_deleted_post_still_has_its_text_blanked(
    client, db, auth_headers, student2_headers, enrolled
):
    pid = _participacion(client, auth_headers).json()["id"]
    # A reply keeps the thread reachable after deletion; without one the
    # endpoint 404s and there is nothing to assert against.
    client.post("/api/posts", data={"content": "buena", "parent_id": str(pid)},
                headers=student2_headers)
    client.delete(f"/api/posts/{pid}", headers=auth_headers)
    body = client.get(f"/api/posts/{pid}", headers=auth_headers).json()["post"]
    assert body["content"] == ""
