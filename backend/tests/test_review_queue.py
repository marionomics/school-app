from datetime import datetime, timedelta, timezone

from app.models import Post

DUE = datetime(2026, 8, 9, 23, 59, tzinfo=timezone.utc)


def _tarea(db, teacher, klass):
    p = Post(author_id=teacher.id, class_id=klass.id, type="tarea", content="Cap 3",
             due_date=DUE)
    db.add(p)
    db.commit()
    return p


def _entrega(db, student, tarea, at=DUE - timedelta(hours=2)):
    p = Post(author_id=student.id, class_id=tarea.class_id, type="regular",
             parent_id=tarea.id, content="mi entrega", is_entrega=True, created_at=at)
    db.add(p)
    db.commit()
    return p


def test_entregas_queue_groups_by_tarea(client, db, teacher_headers, teacher, student, klass, enrolled):
    t = _tarea(db, teacher, klass)
    _entrega(db, student, t)
    r = client.get(f"/api/review/entregas?class_id={klass.id}", headers=teacher_headers)
    assert r.status_code == 200, r.text
    groups = r.json()["groups"]
    assert len(groups) == 1
    assert groups[0]["tarea"]["id"] == t.id
    assert groups[0]["pending"] == 1
    assert float(groups[0]["entregas"][0]["auto_score"]) == 100.0
    assert groups[0]["entregas"][0]["reviewed"] is False


def test_reviewed_entregas_drop_out_of_the_unopened_filter(client, db, teacher_headers, teacher, student, klass, enrolled):
    t = _tarea(db, teacher, klass)
    e = _entrega(db, student, t)
    client.put("/api/reviews", json={"item_post_id": t.id, "student_id": student.id,
                                     "entrega_post_id": e.id, "score": 100},
               headers=teacher_headers)
    r = client.get(f"/api/review/entregas?class_id={klass.id}&status=unopened",
                   headers=teacher_headers)
    assert r.json()["groups"] == []
    r = client.get(f"/api/review/entregas?class_id={klass.id}&status=all",
                   headers=teacher_headers)
    assert r.json()["groups"][0]["entregas"][0]["reviewed"] is True


def test_examenes_list_returns_the_classes_examenes(client, db, teacher_headers, teacher, klass):
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen", content="P1",
             examen_mode="paper")
    db.add(x)
    db.commit()
    r = client.get(f"/api/review/examenes?class_id={klass.id}", headers=teacher_headers)
    assert r.status_code == 200
    assert [i["id"] for i in r.json()["items"]] == [x.id]
    assert r.json()["items"][0]["examen_mode"] == "paper"


def test_examen_roster_lists_every_active_enrollment(client, db, teacher_headers, teacher, student, student2, klass, enrolled):
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen", content="P1",
             examen_mode="paper")
    db.add(x)
    db.commit()
    r = client.get(f"/api/review/examenes/{x.id}", headers=teacher_headers)
    assert r.status_code == 200
    ids = {row["student"]["id"] for row in r.json()["rows"]}
    assert {student.id, student2.id} <= ids
    assert r.json()["examen"]["graded_at"] is None


def test_participaciones_list_shows_veto_state(client, db, teacher_headers, auth_headers, klass, enrolled):
    pid = client.post("/api/posts", data={"content": "Participé explicando el modelo",
                                          "type": "participacion", "taps": "2"},
                      headers=auth_headers).json()["id"]
    client.post(f"/api/posts/{pid}/veto", json={"reason": "no aplica"}, headers=teacher_headers)
    # A vetoed participación is handled, so it has left the pending queue.
    r = client.get(f"/api/review/participaciones?class_id={klass.id}&status=handled",
                   headers=teacher_headers)
    row = next(i for i in r.json()["items"] if i["post_id"] == pid)
    assert row["vetoed"] is True
    assert row["veto_reason"] == "no aplica"
    assert row["taps"] == 2


def test_another_teacher_cannot_read_the_queue(client, db, klass, teacher):
    from app.auth.sessions import create_session
    from app.models import User

    other = User(google_id="g-other", email="otro@example.com", name="Otro", role="teacher")
    db.add(other)
    db.commit()
    headers = {"Authorization": f"Bearer {create_session(db, other)}"}
    r = client.get(f"/api/review/entregas?class_id={klass.id}", headers=headers)
    assert r.status_code == 403


def test_student_cannot_read_the_queue(client, auth_headers, klass, enrolled):
    r = client.get(f"/api/review/entregas?class_id={klass.id}", headers=auth_headers)
    assert r.status_code == 403


def _part(client, headers, text="Participé explicando el modelo"):
    return client.post("/api/posts", data={
        "content": text, "type": "participacion", "taps": "2",
    }, headers=headers).json()["id"]


def test_pending_excludes_reviewed_and_vetoed(client, db, teacher_headers, auth_headers, klass, enrolled):
    plain = _part(client, auth_headers)
    seen = _part(client, auth_headers)
    killed = _part(client, auth_headers)
    client.post(f"/api/posts/{seen}/reviewed", headers=teacher_headers)
    client.post(f"/api/posts/{killed}/veto", headers=teacher_headers)

    r = client.get(f"/api/review/participaciones?class_id={klass.id}&status=pending",
                   headers=teacher_headers)
    ids = [i["post_id"] for i in r.json()["items"]]
    assert plain in ids
    assert seen not in ids
    assert killed not in ids


def test_handled_holds_both_reviewed_and_vetoed(client, db, teacher_headers, auth_headers, klass, enrolled):
    seen = _part(client, auth_headers)
    killed = _part(client, auth_headers)
    client.post(f"/api/posts/{seen}/reviewed", headers=teacher_headers)
    client.post(f"/api/posts/{killed}/veto", headers=teacher_headers)

    r = client.get(f"/api/review/participaciones?class_id={klass.id}&status=handled",
                   headers=teacher_headers)
    ids = [i["post_id"] for i in r.json()["items"]]
    assert seen in ids and killed in ids


def test_a_deleted_participacion_is_in_neither_list(client, db, teacher_headers, auth_headers, klass, enrolled):
    # No evidence, nothing to review: the feed never shows it, so it could
    # never be cleared and /revisar would never empty.
    gone = _part(client, auth_headers)
    seen_then_gone = _part(client, auth_headers)
    client.post(f"/api/posts/{seen_then_gone}/reviewed", headers=teacher_headers)
    for pid in (gone, seen_then_gone):
        assert client.delete(f"/api/posts/{pid}", headers=auth_headers).status_code == 204

    for status in ("pending", "handled"):
        r = client.get(f"/api/review/participaciones?class_id={klass.id}&status={status}",
                       headers=teacher_headers)
        ids = [i["post_id"] for i in r.json()["items"]]
        assert gone not in ids and seen_then_gone not in ids, status


def test_rows_carry_the_reviewed_flag(client, db, teacher_headers, auth_headers, klass, enrolled):
    seen = _part(client, auth_headers)
    client.post(f"/api/posts/{seen}/reviewed", headers=teacher_headers)
    r = client.get(f"/api/review/participaciones?class_id={klass.id}&status=handled",
                   headers=teacher_headers)
    row = next(i for i in r.json()["items"] if i["post_id"] == seen)
    assert row["reviewed"] is True
    assert row["vetoed"] is False


def _examen(db, teacher, klass, mode="paper"):
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen", content="P1",
             examen_mode=mode)
    db.add(x)
    db.commit()
    return x


def _reply(db, student, parent, content, at, is_entrega=False, files=(), status="active"):
    from app.models import Attachment

    p = Post(author_id=student.id, class_id=parent.class_id, type="regular",
             parent_id=parent.id, content=content, is_entrega=is_entrega,
             created_at=at, status=status)
    db.add(p)
    db.flush()
    for name in files:
        db.add(Attachment(post_id=p.id, file_key=f"k/{name}", file_name=name,
                          file_size=10, mime_type="application/pdf"))
    db.commit()
    return p


def _roster_row(client, headers, examen, student):
    r = client.get(f"/api/review/examenes/{examen.id}", headers=headers)
    assert r.status_code == 200, r.text
    return next(row for row in r.json()["rows"] if row["student"]["id"] == student.id)


def test_roster_shows_an_examen_reply_with_files_even_without_the_entrega_toggle(
        client, db, teacher_headers, teacher, student, klass, enrolled):
    # Bug 8: students answered the examen thread with files and the roster only
    # showed a score box. Nobody told them to flip is_entrega, and they should
    # not have to.
    for mode in ("paper", "digital"):
        x = _examen(db, teacher, klass, mode)
        reply = _reply(db, student, x, "mis respuestas", DUE, files=["examen.pdf"])
        sub = _roster_row(client, teacher_headers, x, student)["submission"]
        assert sub["post_id"] == reply.id
        assert sub["content"] == "mis respuestas"
        assert [a["file_name"] for a in sub["attachments"]] == ["examen.pdf"]


def test_roster_prefers_the_marked_entrega_over_a_later_reply_with_files(
        client, db, teacher_headers, teacher, student, klass, enrolled):
    x = _examen(db, teacher, klass)
    entrega = _reply(db, student, x, "entrega", DUE, is_entrega=True)
    _reply(db, student, x, "otra cosa", DUE + timedelta(hours=1), files=["foto.jpg"])
    assert _roster_row(client, teacher_headers, x, student)["submission"]["post_id"] == entrega.id


def test_roster_falls_to_the_latest_reply_with_files(
        client, db, teacher_headers, teacher, student, klass, enrolled):
    x = _examen(db, teacher, klass)
    _reply(db, student, x, "v1", DUE, files=["v1.pdf"])
    _reply(db, student, x, "sólo texto", DUE + timedelta(hours=2))
    _reply(db, student, x, "borrada", DUE + timedelta(hours=3), files=["b.pdf"],
           status="deleted")
    v2 = _reply(db, student, x, "v2", DUE + timedelta(hours=1), files=["v2.pdf"])
    assert _roster_row(client, teacher_headers, x, student)["submission"]["post_id"] == v2.id


def test_roster_row_without_anything_uploaded_is_still_gradable(
        client, db, teacher_headers, teacher, student, klass, enrolled):
    x = _examen(db, teacher, klass, "digital")
    _reply(db, student, x, "¿es para hoy?", DUE)   # a question, not an answer
    row = _roster_row(client, teacher_headers, x, student)
    assert row["submission"] is None
    assert row["score"] is None
