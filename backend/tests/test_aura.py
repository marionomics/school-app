from datetime import date, datetime, timezone
from decimal import Decimal

from app.models import Class, Like, PointsLedger, Post, User

OLD = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _participacion(client, headers):
    r = client.post("/api/posts", data={
        "content": "Expliqué el modelo de oferta y demanda",
        "type": "participacion", "taps": "3",
    }, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _state(db, pid, teacher):
    """(teacher has a like on it, it is validated) — the two must always agree."""
    db.expire_all()
    has_like = db.query(Like).filter_by(user_id=teacher.id, post_id=pid).first() is not None
    return has_like, db.get(Post, pid).reviewed_at is not None


def _active_points(db, user_id) -> Decimal:
    rows = db.query(PointsLedger).filter(PointsLedger.user_id == user_id,
                                         PointsLedger.revoked_at.is_(None)).all()
    return sum((r.points for r in rows), Decimal("0"))


def test_every_entry_point_keeps_aura_and_validation_in_sync(
        client, db, teacher, teacher_headers, auth_headers, student, enrolled):
    pid = _participacion(client, auth_headers)
    before = _active_points(db, student.id)

    r = client.post(f"/api/posts/{pid}/like", headers=teacher_headers)
    assert r.json() == {"liked": True, "like_count": 1}
    assert _state(db, pid, teacher) == (True, True)

    client.post(f"/api/posts/{pid}/like", headers=teacher_headers)
    assert _state(db, pid, teacher) == (False, False)

    client.post(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    assert _state(db, pid, teacher) == (True, True)

    client.delete(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    assert _state(db, pid, teacher) == (False, False)

    r = client.post("/api/review/participaciones/reviewed",
                    json={"post_ids": [pid]}, headers=teacher_headers)
    assert r.status_code == 200, r.text
    assert _state(db, pid, teacher) == (True, True)

    # None of it moved a single point.
    assert _active_points(db, student.id) == before


def test_removing_the_aura_returns_it_to_pending(
        client, db, klass, teacher_headers, auth_headers, enrolled):
    pid = _participacion(client, auth_headers)
    client.post(f"/api/posts/{pid}/like", headers=teacher_headers)
    client.post(f"/api/posts/{pid}/like", headers=teacher_headers)
    r = client.get(f"/api/review/participaciones?class_id={klass.id}&status=pending",
                   headers=teacher_headers)
    assert pid in [i["post_id"] for i in r.json()["items"]]


def test_teacher_aura_on_a_regular_post_does_not_validate(
        client, db, teacher, teacher_headers, auth_headers, enrolled):
    pid = client.post("/api/posts", data={"content": "hola a todos"},
                      headers=auth_headers).json()["id"]
    client.post(f"/api/posts/{pid}/like", headers=teacher_headers)
    assert _state(db, pid, teacher) == (True, False)


def test_validating_twice_counts_one_aura(
        client, db, teacher, teacher_headers, auth_headers, enrolled):
    pid = _participacion(client, auth_headers)
    client.post(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    db.expire_all()
    first = db.get(Post, pid).reviewed_at
    client.post(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    client.post("/api/review/participaciones/reviewed",
                json={"post_ids": [pid]}, headers=teacher_headers)
    db.expire_all()
    post = db.get(Post, pid)
    assert post.like_count == 1
    assert post.reviewed_at == first


def test_unvalidating_without_a_like_row_keeps_the_count(
        client, db, teacher, teacher_headers, auth_headers, student2_headers, enrolled):
    # Old data: validated before aura existed, so no teacher like row — but a
    # classmate's aura is there and must survive.
    pid = _participacion(client, auth_headers)
    client.post(f"/api/posts/{pid}/like", headers=student2_headers)
    db.expire_all()
    post = db.get(Post, pid)
    post.reviewed_at = OLD
    post.reviewed_by = teacher.id
    db.commit()
    client.delete(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    db.expire_all()
    post = db.get(Post, pid)
    assert post.like_count == 1
    assert post.reviewed_at is None


def test_validating_a_vetoed_participacion_stays_in_sync_and_moves_no_points(
        client, db, teacher, teacher_headers, auth_headers, student, enrolled):
    pid = _participacion(client, auth_headers)
    client.post(f"/api/posts/{pid}/veto", json={"reason": "no aplica"}, headers=teacher_headers)
    before = _active_points(db, student.id)
    client.post(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    assert _state(db, pid, teacher) == (True, True)
    assert _active_points(db, student.id) == before


def test_veto_keeps_the_teachers_aura_and_unveto_restores_the_post(
        client, db, teacher, teacher_headers, auth_headers, enrolled):
    pid = _participacion(client, auth_headers)
    client.post(f"/api/posts/{pid}/like", headers=teacher_headers)
    client.post(f"/api/posts/{pid}/veto", json={}, headers=teacher_headers)
    assert _state(db, pid, teacher) == (True, True)
    client.delete(f"/api/posts/{pid}/veto", headers=teacher_headers)
    assert _state(db, pid, teacher) == (True, True)
    db.expire_all()
    assert db.get(Post, pid).status == "active"


def test_another_teachers_aura_does_not_validate(
        client, db, teacher, auth_headers, enrolled):
    from app.auth.sessions import create_session

    other = User(google_id="g-other-aura", email="otra@example.com", name="Otra", role="teacher")
    db.add(other)
    db.commit()
    db.add(Class(name="Otra", code="OTRAAURA26", teacher_id=other.id,
                 start_date=date(2026, 8, 17), end_date=date(2026, 12, 4), schedule_json=[]))
    db.commit()
    headers = {"Authorization": f"Bearer {create_session(db, other)}"}
    pid = _participacion(client, auth_headers)
    r = client.post(f"/api/posts/{pid}/like", headers=headers)
    assert r.json()["liked"] is True
    db.expire_all()
    assert db.get(Post, pid).reviewed_at is None


def _set_old(db, pid):
    post = db.get(Post, pid)
    post.last_activity_at = OLD
    db.commit()


def _activity(db, pid):
    """As an aware UTC datetime: SQLite hands back naive values, PostgreSQL
    (CI, prod) aware ones in the session's zone — compare instants, not
    wall-clock strings."""
    db.expire_all()
    dt = db.get(Post, pid).last_activity_at
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def test_no_aura_bumps_the_feed(
        client, db, teacher_headers, auth_headers, student2_headers, enrolled, student2):
    pid = _participacion(client, auth_headers)
    _set_old(db, pid)
    client.post(f"/api/posts/{pid}/like", headers=student2_headers)
    client.post(f"/api/posts/{pid}/like", headers=teacher_headers)
    client.post(f"/api/posts/{pid}/reviewed", headers=teacher_headers)
    assert _activity(db, pid) == OLD


def test_a_reply_still_bumps_the_feed(client, db, auth_headers, student2_headers, enrolled, student2):
    pid = client.post("/api/posts", data={"content": "pregunta abierta"},
                      headers=auth_headers).json()["id"]
    _set_old(db, pid)
    client.post("/api/posts", data={"content": "respuesta", "parent_id": str(pid)},
                headers=student2_headers)
    assert _activity(db, pid) > OLD
