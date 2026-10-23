"""Accepting the suggested (lateness) score for every entrega on screen in
one tap. The grade doesn't change — an ungraded entrega already counts with
that score — it only becomes a grade the teacher gave."""
from datetime import datetime, timedelta, timezone

from app.models import Class, Post, Review

DUE = datetime(2026, 8, 9, 23, 59, tzinfo=timezone.utc)
URL = "/api/reviews/accept-suggested"


def _tarea(db, teacher, klass, due=DUE):
    p = Post(author_id=teacher.id, class_id=klass.id, type="tarea", content="t", due_date=due)
    db.add(p)
    db.commit()
    return p


def _entrega(db, student, tarea, at=DUE - timedelta(hours=1)):
    p = Post(author_id=student.id, class_id=tarea.class_id, type="regular",
             parent_id=tarea.id, content="e", is_entrega=True, created_at=at)
    db.add(p)
    db.commit()
    return p


def _review(db, tarea, student):
    return (db.query(Review)
            .filter(Review.item_post_id == tarea.id, Review.student_id == student.id).first())


def test_grades_each_entrega_with_its_suggested_score(
        client, db, teacher_headers, teacher, student, student2, klass, enrolled):
    t = _tarea(db, teacher, klass)
    on_time = _entrega(db, student, t)
    late = _entrega(db, student2, t, at=DUE + timedelta(days=2))
    r = client.post(URL, json={"item_post_id": t.id, "entrega_post_ids": [on_time.id, late.id]},
                    headers=teacher_headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"graded": 2}
    a, b = _review(db, t, student), _review(db, t, student2)
    assert float(a.score) == 100 and a.entrega_post_id == on_time.id
    assert float(b.score) == 50 and b.entrega_post_id == late.id


def test_never_overwrites_a_grade_already_given(
        client, db, teacher_headers, teacher, student, klass, enrolled):
    t = _tarea(db, teacher, klass)
    e = _entrega(db, student, t)
    db.add(Review(item_post_id=t.id, student_id=student.id, entrega_post_id=e.id,
                  reviewer_id=teacher.id, score=70, feedback="ojo"))
    db.commit()
    r = client.post(URL, json={"item_post_id": t.id, "entrega_post_ids": [e.id]},
                    headers=teacher_headers)
    assert r.json() == {"graded": 0}
    assert float(_review(db, t, student).score) == 70


def test_only_what_was_sent(client, db, teacher_headers, teacher, student, student2, klass, enrolled):
    t = _tarea(db, teacher, klass)
    seen = _entrega(db, student, t)
    _entrega(db, student2, t)  # arrived after the teacher looked
    client.post(URL, json={"item_post_id": t.id, "entrega_post_ids": [seen.id]},
                headers=teacher_headers)
    assert _review(db, t, student2) is None


def test_a_replaced_entrega_is_skipped(client, db, teacher_headers, teacher, student, klass, enrolled):
    t = _tarea(db, teacher, klass)
    old = _entrega(db, student, t, at=DUE - timedelta(hours=5))
    _entrega(db, student, t, at=DUE - timedelta(hours=1))
    r = client.post(URL, json={"item_post_id": t.id, "entrega_post_ids": [old.id]},
                    headers=teacher_headers)
    assert r.json() == {"graded": 0}
    assert _review(db, t, student) is None


def test_a_ghost_entrega_is_skipped(client, db, teacher_headers, teacher, ghost, klass):
    t = _tarea(db, teacher, klass)
    e = _entrega(db, ghost, t)
    r = client.post(URL, json={"item_post_id": t.id, "entrega_post_ids": [e.id]},
                    headers=teacher_headers)
    assert r.json() == {"graded": 0}


def test_another_tareas_entrega_rejects_the_batch(
        client, db, teacher_headers, teacher, student, student2, klass, enrolled):
    t1, t2 = _tarea(db, teacher, klass), _tarea(db, teacher, klass)
    mine = _entrega(db, student, t1)
    other = _entrega(db, student2, t2)
    r = client.post(URL, json={"item_post_id": t1.id, "entrega_post_ids": [mine.id, other.id]},
                    headers=teacher_headers)
    assert r.status_code == 422
    assert _review(db, t1, student) is None


def test_only_the_classes_teacher(client, db, auth_headers, teacher, student, klass, enrolled):
    t = _tarea(db, teacher, klass)
    e = _entrega(db, student, t)
    r = client.post(URL, json={"item_post_id": t.id, "entrega_post_ids": [e.id]},
                    headers=auth_headers)
    assert r.status_code == 403


def test_a_tarea_without_due_date_has_no_suggestion(
        client, db, teacher_headers, teacher, student, klass, enrolled):
    t = _tarea(db, teacher, klass, due=None)
    e = _entrega(db, student, t)
    r = client.post(URL, json={"item_post_id": t.id, "entrega_post_ids": [e.id]},
                    headers=teacher_headers)
    assert r.status_code == 422


def test_it_leaves_the_teachers_pending_list(
        client, db, teacher_headers, teacher, student, klass, enrolled):
    t = _tarea(db, teacher, klass)
    e = _entrega(db, student, t)
    client.post(URL, json={"item_post_id": t.id, "entrega_post_ids": [e.id]},
                headers=teacher_headers)
    items = client.get("/api/feed?limit=50", headers=teacher_headers).json()["items"]
    assert all(p["pending_count"] is None for p in items)
