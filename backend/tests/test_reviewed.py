from decimal import Decimal

from app.models import PointsLedger, Post


def _participacion(client, headers):
    return client.post("/api/posts", data={
        "content": "Expliqué el modelo de oferta y demanda",
        "type": "participacion", "taps": "3",
    }, headers=headers)


def _active_points(db, user_id) -> Decimal:
    rows = db.query(PointsLedger).filter(PointsLedger.user_id == user_id,
                                         PointsLedger.revoked_at.is_(None)).all()
    return sum((r.points for r in rows), Decimal("0"))


def test_reviewing_moves_no_points(client, db, teacher_headers, auth_headers, student, enrolled):
    """The whole point of validar: it records attention, never a grade.

    If this test ever fails, the change that broke it is wrong — this is the
    guard that keeps validar from drifting into being an approval gate."""
    pid = _participacion(client, auth_headers).json()["id"]
    before = _active_points(db, student.id)
    r = client.post(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    assert r.status_code == 200
    assert r.json()["reviewed"] is True
    db.expire_all()
    assert _active_points(db, student.id) == before
    assert db.get(Post, pid).status == "active"


def test_unreviewing_returns_it_to_pending(client, db, teacher_headers, auth_headers, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    client.post(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    r = client.delete(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    assert r.json()["reviewed"] is False
    db.expire_all()
    assert db.get(Post, pid).reviewed_at is None
    assert db.get(Post, pid).reviewed_by is None


def test_reviewing_records_who_looked(client, db, teacher_headers, auth_headers, teacher, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    client.post(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    db.expire_all()
    assert db.get(Post, pid).reviewed_by == teacher.id


def test_a_student_cannot_review(client, auth_headers, student2_headers, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    r = client.post(f"/api/posts/{pid}/reviewed", headers=student2_headers)
    assert r.status_code == 403


def test_only_participaciones_can_be_reviewed(client, db, teacher_headers, auth_headers, enrolled):
    pid = client.post("/api/posts", data={"content": "hola"},
                      headers=auth_headers).json()["id"]
    r = client.post(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    assert r.status_code == 422


def test_reviewing_and_vetoing_are_independent(client, db, teacher_headers, auth_headers, student, enrolled):
    """Both facts coexist: a post can be seen and still count, or be cancelled
    without ever having been marked seen."""
    pid = _participacion(client, auth_headers).json()["id"]
    client.post(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    client.post(f"/api/posts/{pid}/veto", headers=teacher_headers)
    db.expire_all()
    post = db.get(Post, pid)
    assert post.reviewed_at is not None      # still marked as seen
    assert post.status == "vetoed"           # and cancelled
    assert _active_points(db, student.id) == Decimal("0")
