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
