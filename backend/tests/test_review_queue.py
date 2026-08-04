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


def test_rows_carry_the_reviewed_flag(client, db, teacher_headers, auth_headers, klass, enrolled):
    seen = _part(client, auth_headers)
    client.post(f"/api/posts/{seen}/reviewed", headers=teacher_headers)
    r = client.get(f"/api/review/participaciones?class_id={klass.id}&status=handled",
                   headers=teacher_headers)
    row = next(i for i in r.json()["items"] if i["post_id"] == seen)
    assert row["reviewed"] is True
    assert row["vetoed"] is False
