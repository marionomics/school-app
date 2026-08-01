from datetime import datetime, timedelta, timezone

from app.models import Post

DUE = datetime(2026, 8, 9, 23, 59, tzinfo=timezone.utc)


def _tarea(db, teacher, klass):
    p = Post(author_id=teacher.id, class_id=klass.id, type="tarea",
             content="t", due_date=DUE)
    db.add(p)
    db.commit()
    return p


def _entrega(db, student, tarea, at=DUE - timedelta(hours=1)):
    p = Post(author_id=student.id, class_id=tarea.class_id, type="regular",
             parent_id=tarea.id, content="e", is_entrega=True, created_at=at)
    db.add(p)
    db.commit()
    return p


def _body(tarea, student, entrega=None, score=90, feedback=None):
    return {"item_post_id": tarea.id, "student_id": student.id,
            "entrega_post_id": entrega.id if entrega else None,
            "score": score, "feedback": feedback}


def test_teacher_scores_an_entrega(client, db, teacher_headers, teacher, student, klass, enrolled):
    t = _tarea(db, teacher, klass)
    e = _entrega(db, student, t)
    r = client.put("/api/reviews", json=_body(t, student, e, 85, "bien"),
                   headers=teacher_headers)
    assert r.status_code == 200, r.text
    assert float(r.json()["score"]) == 85.0
    assert r.json()["feedback"] == "bien"


def test_second_write_updates_instead_of_duplicating(client, db, teacher_headers, teacher, student, klass, enrolled):
    from app.models import Review

    t = _tarea(db, teacher, klass)
    e = _entrega(db, student, t)
    first = client.put("/api/reviews", json=_body(t, student, e, 85), headers=teacher_headers)
    second = client.put("/api/reviews", json=_body(t, student, e, 95), headers=teacher_headers)
    assert first.json()["id"] == second.json()["id"]
    assert float(second.json()["score"]) == 95.0
    assert db.query(Review).count() == 1


def test_tarea_score_above_100_is_rejected(client, db, teacher_headers, teacher, student, klass, enrolled):
    t = _tarea(db, teacher, klass)
    e = _entrega(db, student, t)
    r = client.put("/api/reviews", json=_body(t, student, e, 120), headers=teacher_headers)
    assert r.status_code == 422
    assert "0" in r.json()["detail"] and "100" in r.json()["detail"]


def test_examen_score_above_10_is_rejected(client, db, teacher_headers, teacher, student, klass, enrolled):
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen",
             content="p", examen_mode="paper")
    db.add(x)
    db.commit()
    r = client.put("/api/reviews",
                   json={"item_post_id": x.id, "student_id": student.id, "score": 85},
                   headers=teacher_headers)
    assert r.status_code == 422


def test_paper_examen_review_needs_no_entrega(client, db, teacher_headers, teacher, student, klass, enrolled):
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen",
             content="p", examen_mode="paper")
    db.add(x)
    db.commit()
    r = client.put("/api/reviews",
                   json={"item_post_id": x.id, "student_id": student.id, "score": 9},
                   headers=teacher_headers)
    assert r.status_code == 200
    assert r.json()["entrega_post_id"] is None


def test_student_cannot_write_a_review(client, db, auth_headers, teacher, student, klass, enrolled):
    t = _tarea(db, teacher, klass)
    e = _entrega(db, student, t)
    r = client.put("/api/reviews", json=_body(t, student, e), headers=auth_headers)
    assert r.status_code == 403


def test_reviewing_a_student_not_enrolled_is_rejected(client, db, teacher_headers, teacher, student, klass):
    # no `enrolled` fixture: the student is not in the class
    t = _tarea(db, teacher, klass)
    r = client.put("/api/reviews", json=_body(t, student, None), headers=teacher_headers)
    assert r.status_code == 422
