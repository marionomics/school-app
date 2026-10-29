from datetime import datetime, timezone

from app.auth.sessions import create_session
from app.models import Enrollment, Post, PostMention, User
from app.services.grades import _counting_entrega

DUE = datetime(2030, 8, 9, 23, 59, tzinfo=timezone.utc)


def _user(db, klass, handle):
    u = User(google_id=f"g-{handle}", email=f"{handle}@example.com",
             name=handle.title(), username=handle)
    db.add(u)
    db.flush()
    db.add(Enrollment(user_id=u.id, class_id=klass.id))
    db.commit()
    return u


def _setup(db, teacher, klass):
    ana, pedro, luis = (_user(db, klass, n) for n in ("ana", "pedro", "luis"))
    t = Post(author_id=teacher.id, class_id=klass.id, type="tarea", content="T", due_date=DUE)
    db.add(t)
    db.flush()
    e = Post(author_id=ana.id, class_id=klass.id, parent_id=t.id, content="@pedro",
             is_entrega=True, created_at=DUE)
    db.add(e)
    db.flush()
    db.add(PostMention(post_id=e.id, user_id=pedro.id, kind="team"))
    db.commit()
    return ana, pedro, luis, t, e


def test_remove_then_restore(client, db, teacher, teacher_headers, klass):
    ana, pedro, _, t, e = _setup(db, teacher, klass)
    r = client.post(f"/api/posts/{e.id}/team/{pedro.id}/remove", headers=teacher_headers)
    assert r.status_code == 200, r.text
    assert r.json()["mentions"][0]["removed"] is True
    assert _counting_entrega(db, pedro.id, t.id) is None
    m = db.query(PostMention).one()
    assert m.removed_by == teacher.id
    r = client.post(f"/api/posts/{e.id}/team/{pedro.id}/restore", headers=teacher_headers)
    assert r.status_code == 200, r.text
    assert r.json()["mentions"][0]["removed"] is False
    assert _counting_entrega(db, pedro.id, t.id).id == e.id


def test_restore_refused_when_on_another_team(client, db, teacher, teacher_headers, klass):
    ana, pedro, luis, t, e = _setup(db, teacher, klass)
    client.post(f"/api/posts/{e.id}/team/{pedro.id}/remove", headers=teacher_headers)
    other = Post(author_id=luis.id, class_id=klass.id, parent_id=t.id, content="@pedro",
                 is_entrega=True, created_at=DUE)
    db.add(other)
    db.flush()
    db.add(PostMention(post_id=other.id, user_id=pedro.id, kind="team"))
    db.commit()
    r = client.post(f"/api/posts/{e.id}/team/{pedro.id}/restore", headers=teacher_headers)
    assert r.status_code == 409
    assert "@luis" in r.json()["detail"]


def test_only_the_teacher_and_only_team_mentions(client, db, teacher, teacher_headers, klass):
    ana, pedro, luis, t, e = _setup(db, teacher, klass)
    h = {"Authorization": f"Bearer {create_session(db, ana)}"}
    assert client.post(f"/api/posts/{e.id}/team/{pedro.id}/remove", headers=h).status_code == 403
    assert client.post(f"/api/posts/{e.id}/team/{luis.id}/remove",
                       headers=teacher_headers).status_code == 404
