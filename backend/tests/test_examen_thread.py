"""Grading an examen from its thread: the reply the roster counts as the
student's work is the one the thread marks, so "Calificar" sits on it."""
from datetime import datetime, timedelta, timezone

from app.models import Attachment, Post

DUE = datetime(2026, 8, 9, 23, 59, tzinfo=timezone.utc)


def _examen(db, teacher, klass):
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen", content="P1",
             examen_mode="digital")
    db.add(x)
    db.commit()
    return x


def _reply(db, student, parent, content, at, is_entrega=False, files=()):
    p = Post(author_id=student.id, class_id=parent.class_id, type="regular",
             parent_id=parent.id, content=content, is_entrega=is_entrega, created_at=at)
    db.add(p)
    db.flush()
    for name in files:
        db.add(Attachment(post_id=p.id, file_key=f"k/{name}", file_name=name,
                          file_size=10, mime_type="application/pdf"))
    db.commit()
    return p


def _thread(client, headers, post_id):
    r = client.get(f"/api/posts/{post_id}", headers=headers)
    assert r.status_code == 200, r.text
    return {x["id"]: x for x in r.json()["replies"]}


def test_the_latest_reply_with_files_is_the_submission(
        client, db, teacher_headers, teacher, student, klass, enrolled):
    x = _examen(db, teacher, klass)
    v1 = _reply(db, student, x, "v1", DUE, files=["v1.pdf"])
    v2 = _reply(db, student, x, "v2", DUE + timedelta(hours=1), files=["v2.pdf"])
    q = _reply(db, student, x, "¿así?", DUE + timedelta(hours=2))
    replies = _thread(client, teacher_headers, x.id)
    assert replies[v2.id]["is_submission"] is True
    assert replies[v1.id]["is_submission"] is False
    assert replies[q.id]["is_submission"] is False


def test_a_marked_entrega_wins_over_a_later_upload(
        client, db, teacher_headers, teacher, student, klass, enrolled):
    x = _examen(db, teacher, klass)
    entrega = _reply(db, student, x, "entrega", DUE, is_entrega=True)
    later = _reply(db, student, x, "foto", DUE + timedelta(hours=1), files=["f.jpg"])
    replies = _thread(client, teacher_headers, x.id)
    assert replies[entrega.id]["is_submission"] is True
    assert replies[later.id]["is_submission"] is False


def test_the_submission_carries_the_roster_score(
        client, db, teacher_headers, teacher, student, klass, enrolled):
    x = _examen(db, teacher, klass)
    sub = _reply(db, student, x, "v1", DUE, files=["v1.pdf"])
    # The roster saves with no entrega_post_id; the thread must still show it.
    client.put("/api/reviews", json={"item_post_id": x.id, "student_id": student.id,
                                     "score": 8}, headers=teacher_headers)
    replies = _thread(client, teacher_headers, x.id)
    assert float(replies[sub.id]["my_review"]["score"]) == 8.0


def test_students_see_no_submission_marks_nor_scores(
        client, db, teacher_headers, auth_headers, student2_headers, teacher, student,
        klass, enrolled):
    # Until the teacher marks the examen calificado the score is not released.
    x = _examen(db, teacher, klass)
    sub = _reply(db, student, x, "v1", DUE, files=["v1.pdf"])
    client.put("/api/reviews", json={"item_post_id": x.id, "student_id": student.id,
                                     "score": 8}, headers=teacher_headers)
    for headers in (auth_headers, student2_headers):
        reply = _thread(client, headers, x.id)[sub.id]
        assert reply["is_submission"] is False
        assert reply["my_review"] is None


def test_a_tarea_thread_marks_nothing_as_submission(
        client, db, teacher_headers, teacher, student, klass, enrolled):
    t = Post(author_id=teacher.id, class_id=klass.id, type="tarea", content="Cap 3",
             due_date=DUE)
    db.add(t)
    db.commit()
    e = _reply(db, student, t, "mi entrega", DUE, is_entrega=True)
    assert _thread(client, teacher_headers, t.id)[e.id]["is_submission"] is False
