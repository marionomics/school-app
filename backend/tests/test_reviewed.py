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


def test_bulk_reviews_every_id_sent(client, db, teacher_headers, auth_headers, enrolled):
    ids = [_participacion(client, auth_headers).json()["id"] for _ in range(3)]
    r = client.post("/api/review/participaciones/reviewed",
                    json={"post_ids": ids}, headers=teacher_headers)
    assert r.status_code == 200, r.text
    assert r.json()["reviewed"] == 3
    db.expire_all()
    assert all(db.get(Post, i).reviewed_at is not None for i in ids)


def test_bulk_with_a_foreign_id_writes_nothing(client, db, teacher_headers, auth_headers, enrolled):
    """All-or-nothing: a partial write would leave the teacher unable to tell
    which taps landed."""
    from datetime import date

    from app.auth.sessions import create_session
    from app.models import Class, Enrollment, User

    other_teacher = User(google_id="g-other3", email="otro3@example.com",
                         name="Otra", role="teacher")
    db.add(other_teacher)
    db.commit()
    other_class = Class(name="Otra", code="OTRA2026X", teacher_id=other_teacher.id,
                        start_date=date(2026, 8, 17), end_date=date(2026, 12, 4),
                        schedule_json=[])
    db.add(other_class)
    db.commit()
    outsider = User(google_id="g-out", email="out@example.com", name="Out")
    db.add(outsider)
    db.commit()
    db.add(Enrollment(user_id=outsider.id, class_id=other_class.id))
    db.commit()
    out_headers = {"Authorization": f"Bearer {create_session(db, outsider)}"}
    foreign = client.post("/api/posts", data={
        "content": "Participación de otra clase", "type": "participacion",
        "taps": "1",
    }, headers=out_headers).json()["id"]

    mine = _participacion(client, auth_headers).json()["id"]
    r = client.post("/api/review/participaciones/reviewed",
                    json={"post_ids": [mine, foreign]}, headers=teacher_headers)
    assert r.status_code == 403
    db.expire_all()
    assert db.get(Post, mine).reviewed_at is None      # nothing written
    assert db.get(Post, foreign).reviewed_at is None


def test_bulk_with_an_empty_list_is_a_no_op(client, teacher_headers):
    r = client.post("/api/review/participaciones/reviewed",
                    json={"post_ids": []}, headers=teacher_headers)
    assert r.status_code == 200
    assert r.json()["reviewed"] == 0


def test_a_student_cannot_bulk_review(client, auth_headers, student2_headers, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    r = client.post("/api/review/participaciones/reviewed",
                    json={"post_ids": [pid]}, headers=student2_headers)
    assert r.status_code == 403
