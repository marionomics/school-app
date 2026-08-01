from datetime import datetime, timedelta, timezone

from app.models import Post

DUE = datetime(2026, 8, 9, 23, 59, tzinfo=timezone.utc)


def _graded_entrega(client, db, teacher, teacher_headers, student, klass):
    t = Post(author_id=teacher.id, class_id=klass.id, type="tarea", content="Cap 3",
             due_date=DUE)
    db.add(t)
    db.commit()
    e = Post(author_id=student.id, class_id=klass.id, type="regular", parent_id=t.id,
             content="mi entrega", is_entrega=True, created_at=DUE - timedelta(hours=1))
    db.add(e)
    db.commit()
    client.put("/api/reviews",
               json={"item_post_id": t.id, "student_id": student.id,
                     "entrega_post_id": e.id, "score": 88, "feedback": "muy bien"},
               headers=teacher_headers)
    return t, e


def _reply(thread_json, post_id):
    return next(r for r in thread_json["replies"] if r["id"] == post_id)


def test_the_author_sees_their_own_score(client, db, teacher, teacher_headers, auth_headers, student, klass, enrolled):
    t, e = _graded_entrega(client, db, teacher, teacher_headers, student, klass)
    r = client.get(f"/api/posts/{t.id}", headers=auth_headers)
    review = _reply(r.json(), e.id)["my_review"]
    assert float(review["score"]) == 88.0
    assert review["feedback"] == "muy bien"


def test_the_teacher_sees_it_too(client, db, teacher, teacher_headers, student, klass, enrolled):
    t, e = _graded_entrega(client, db, teacher, teacher_headers, student, klass)
    r = client.get(f"/api/posts/{t.id}", headers=teacher_headers)
    assert _reply(r.json(), e.id)["my_review"] is not None


def test_a_classmate_sees_nothing(client, db, teacher, teacher_headers, student2_headers, student, klass, enrolled):
    t, e = _graded_entrega(client, db, teacher, teacher_headers, student, klass)
    r = client.get(f"/api/posts/{t.id}", headers=student2_headers)
    assert _reply(r.json(), e.id)["my_review"] is None


def test_veto_reason_is_private_to_the_author(client, db, teacher_headers, auth_headers, student2_headers, enrolled):
    pid = client.post("/api/posts", data={"content": "Participé en clase hoy",
                                          "type": "participacion", "taps": "1"},
                      headers=auth_headers).json()["id"]
    client.post(f"/api/posts/{pid}/veto", json={"reason": "no fue en clase"},
                headers=teacher_headers)
    mine = client.get(f"/api/posts/{pid}", headers=auth_headers).json()["post"]
    theirs = client.get(f"/api/posts/{pid}", headers=student2_headers).json()["post"]
    assert mine["veto_reason"] == "no fue en clase"
    assert theirs["veto_reason"] is None
