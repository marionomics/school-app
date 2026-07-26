from app.models import Like, Post, PointsLedger


def _mk(db, author, klass, **kw):
    p = Post(author_id=author.id, content="c", class_id=klass.id, **kw)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_like_toggle_and_points(client, db, enrolled, klass, student, student2, student2_headers):
    p = _mk(db, student, klass)
    r1 = client.post(f"/api/posts/{p.id}/like", headers=student2_headers)
    assert r1.json() == {"liked": True, "like_count": 1}
    assert db.query(PointsLedger).filter_by(source_type="forum_like",
                                            revoked_at=None).count() == 1
    r2 = client.post(f"/api/posts/{p.id}/like", headers=student2_headers)
    assert r2.json() == {"liked": False, "like_count": 0}
    assert db.query(PointsLedger).filter_by(source_type="forum_like",
                                            revoked_at=None).count() == 0
    assert db.query(Like).count() == 0


def test_self_like_rejected(client, db, auth_headers, enrolled, klass, student):
    p = _mk(db, student, klass)
    assert client.post(f"/api/posts/{p.id}/like", headers=auth_headers).status_code == 400


def test_like_bumps_root(client, db, enrolled, klass, student, student2_headers):
    root = _mk(db, student, klass)
    reply = _mk(db, student, klass, parent_id=root.id)
    before = root.last_activity_at
    client.post(f"/api/posts/{reply.id}/like", headers=student2_headers)
    db.refresh(root)
    assert root.last_activity_at >= before


def test_author_delete_revokes(client, db, auth_headers, enrolled, klass, student, student2, student2_headers):
    p = _mk(db, student, klass, type="participacion", taps=2)
    from app.services import points
    points.award_participacion(db, p)
    db.commit()
    client.post(f"/api/posts/{p.id}/like", headers=student2_headers)
    res = client.delete(f"/api/posts/{p.id}", headers=auth_headers)
    assert res.status_code == 204
    db.refresh(p)
    assert p.status == "deleted"
    assert db.query(PointsLedger).filter(PointsLedger.revoked_at.is_(None)).count() == 0


def test_teacher_delete_is_veto(client, db, teacher_headers, enrolled, klass, student):
    p = _mk(db, student, klass)
    assert client.delete(f"/api/posts/{p.id}", headers=teacher_headers).status_code == 204
    db.refresh(p)
    assert p.status == "vetoed"


def test_stranger_cannot_delete(client, db, enrolled, klass, student, student2_headers):
    p = _mk(db, student, klass)
    assert client.delete(f"/api/posts/{p.id}", headers=student2_headers).status_code == 403


def test_reply_delete_decrements_root(client, db, auth_headers, enrolled, klass, student):
    root = _mk(db, student, klass)
    reply = _mk(db, student, klass, parent_id=root.id)
    root.reply_count = 1
    db.commit()
    client.delete(f"/api/posts/{reply.id}", headers=auth_headers)
    db.refresh(root)
    assert root.reply_count == 0


def test_attachment_url_when_r2_off(client, db, auth_headers, enrolled, klass, student):
    from app.models import Attachment
    p = _mk(db, student, klass)
    a = Attachment(post_id=p.id, file_key="k", file_name="f.pdf", file_size=1,
                   mime_type="application/pdf")
    db.add(a)
    db.commit()
    assert client.get(f"/api/attachments/{a.id}/url", headers=auth_headers).status_code == 400
    assert client.get("/api/attachments/9999/url", headers=auth_headers).status_code == 404
