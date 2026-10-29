"""Publishing parses @mentions; a submission's eligible mentions form the team."""
from datetime import date, datetime, timezone

import pytest

from app import storage
from app.auth.sessions import create_session
from app.models import Class, Enrollment, Post, PostMention, Review, User

DUE = datetime(2030, 8, 9, 23, 59, tzinfo=timezone.utc)


@pytest.fixture()
def r2_on(monkeypatch):
    monkeypatch.setattr(storage, "is_r2_configured", lambda: True)
    monkeypatch.setattr(storage, "upload_bytes", lambda data, key, content_type: None)
    monkeypatch.setattr(storage, "generate_presigned_url",
                        lambda key, expires=3600: f"https://r2.test/{key}")


def _user(db, klass, handle, status="active"):
    u = User(google_id=f"g-{handle}", email=f"{handle}@example.com",
             name=handle.title(), username=handle)
    db.add(u)
    db.flush()
    if klass is not None:
        db.add(Enrollment(user_id=u.id, class_id=klass.id, status=status))
    db.commit()
    return u


def _h(db, u):
    return {"Authorization": f"Bearer {create_session(db, u)}"}


def _tarea(db, teacher, klass):
    t = Post(author_id=teacher.id, class_id=klass.id, type="tarea", content="T", due_date=DUE)
    db.add(t)
    db.commit()
    return t


def _post(client, db, author, content, **data):
    r = client.post("/api/posts", data={"content": content, **data}, headers=_h(db, author))
    assert r.status_code == 201, r.text
    return r.json()


def _kinds(body):
    return {m["user"]["username"]: m["kind"] for m in body["mentions"]}


def test_a_regular_post_stores_social_mentions(client, db, klass):
    ana = _user(db, klass, "ana")
    _user(db, None, "exalumno")       # in no class: social still works
    body = _post(client, db, ana, "hola @Exalumno y @nadie_existe")
    assert _kinds(body) == {"exalumno": "social"}


def test_an_entrega_makes_a_team_of_two_at_most(client, db, teacher, klass):
    ana, pedro, luis, eva = (_user(db, klass, n) for n in ("ana", "pedro", "luis", "eva"))
    t = _tarea(db, teacher, klass)
    body = _post(client, db, ana, "listo @pedro @luis @eva @ana",
                 parent_id=str(t.id), is_entrega="true")
    assert _kinds(body) == {"pedro": "team", "luis": "team", "eva": "social"}


def test_only_active_classmates_join(client, db, teacher, klass):
    ana = _user(db, klass, "ana")
    _user(db, klass, "fantasma", status="ghost")
    _user(db, None, "otra_clase")
    t = _tarea(db, teacher, klass)
    body = _post(client, db, ana, "@fantasma @otra_clase",
                 parent_id=str(t.id), is_entrega="true")
    assert _kinds(body) == {"fantasma": "social", "otra_clase": "social"}


def test_first_team_wins(client, db, teacher, klass):
    ana, pedro, luis = (_user(db, klass, n) for n in ("ana", "pedro", "luis"))
    t = _tarea(db, teacher, klass)
    _post(client, db, ana, "@pedro", parent_id=str(t.id), is_entrega="true")
    body = _post(client, db, luis, "@pedro", parent_id=str(t.id), is_entrega="true")
    assert _kinds(body) == {"pedro": "social"}
    # ...but Ana re-tagging her own team carries it over
    body = _post(client, db, ana, "v2 @pedro", parent_id=str(t.id), is_entrega="true")
    assert _kinds(body) == {"pedro": "team"}


def test_a_question_under_a_tarea_is_only_social(client, db, teacher, klass):
    ana, pedro = _user(db, klass, "ana"), _user(db, klass, "pedro")
    t = _tarea(db, teacher, klass)
    body = _post(client, db, ana, "¿@pedro ya entregaste?", parent_id=str(t.id))
    assert _kinds(body) == {"pedro": "social"}


def test_an_examen_reply_with_files_is_a_submission(client, db, teacher, klass, r2_on):
    ana, pedro = _user(db, klass, "ana"), _user(db, klass, "pedro")
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen", content="P1",
             examen_mode="digital")
    db.add(x)
    db.commit()
    r = client.post("/api/posts",
                    data={"content": "@pedro", "parent_id": str(x.id)},
                    files=[("files", ("r.pdf", b"x" * 10, "application/pdf"))],
                    headers=_h(db, ana))
    assert r.status_code == 201, r.text
    assert _kinds(r.json()) == {"pedro": "team"}


def test_an_inactive_author_forms_no_team(client, db, teacher, klass, r2_on):
    # A polizon cannot post without an active class, so this one is active in
    # another class and only a guest in the examen's.
    polizon = _user(db, klass, "polizon", status="polizon")
    other = Class(name="Otra", code="OTRA2026TEST", teacher_id=teacher.id,
                  start_date=date(2026, 8, 17), end_date=date(2026, 12, 4),
                  schedule_json=[{"day": 1, "start": "10:00", "end": "11:00"}])
    db.add(other)
    db.flush()
    db.add(Enrollment(user_id=polizon.id, class_id=other.id, status="active"))
    db.commit()
    _user(db, klass, "pedro")
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen", content="P1",
             examen_mode="digital")
    db.add(x)
    db.commit()
    r = client.post("/api/posts", data={"content": "@pedro", "parent_id": str(x.id)},
                    files=[("files", ("r.pdf", b"x" * 10, "application/pdf"))],
                    headers=_h(db, polizon))
    assert r.status_code == 201, r.text
    assert _kinds(r.json()) == {"pedro": "social"}


def test_a_member_sees_the_teams_score_in_the_thread(client, db, teacher, teacher_headers, klass):
    ana, pedro, luis = (_user(db, klass, n) for n in ("ana", "pedro", "luis"))
    t = _tarea(db, teacher, klass)
    e = _post(client, db, ana, "@pedro", parent_id=str(t.id), is_entrega="true")
    db.add(Review(item_post_id=t.id, student_id=ana.id, entrega_post_id=e["id"], score=90))
    db.commit()
    def reply(u):
        replies = client.get(f"/api/posts/{t.id}", headers=_h(db, u)).json()["replies"]
        return next(r for r in replies if r["id"] == e["id"])
    assert float(reply(pedro)["my_review"]["score"]) == 90.0
    assert reply(luis)["my_review"] is None


def test_a_deleted_post_keeps_its_mention_rows(client, db, klass):
    ana, pedro = _user(db, klass, "ana"), _user(db, klass, "pedro")
    body = _post(client, db, ana, "hola @pedro")
    client.delete(f"/api/posts/{body['id']}", headers=_h(db, ana))
    # the row stays (never deleted); serialization hides it with the text
    assert db.query(PostMention).filter(PostMention.post_id == body["id"]).count() == 1
