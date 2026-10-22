from datetime import date, timedelta

from app.models import Attachment, Class, Enrollment, Like, Post, Review, User, utcnow


def _mk(db, author, klass, content="x", age_h=0, **kw):
    p = Post(author_id=author.id, content=content, class_id=klass.id,
             created_at=utcnow() - timedelta(hours=age_h), **kw)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _items(client, headers, url="/api/feed?limit=50"):
    return client.get(url, headers=headers).json()["items"]


def _ids(client, headers):
    return [p["id"] for p in _items(client, headers)]


def test_a_student_sees_untouched_above_what_they_gave_aura(
        client, db, auth_headers, enrolled, klass, student, student2):
    liked = _mk(db, student2, klass, "liked", age_h=0)
    old = _mk(db, student2, klass, "old", age_h=24 * 5)
    db.add(Like(user_id=student.id, post_id=liked.id))
    db.commit()
    ids = _ids(client, auth_headers)
    assert ids.index(old.id) < ids.index(liked.id)


def test_a_pending_participacion_goes_on_top_until_validated(
        client, db, teacher_headers, klass, teacher, student, enrolled, student2):
    part = _mk(db, student, klass, "part", age_h=3, type="participacion", taps=1)
    fresh = _mk(db, student2, klass, "fresh", age_h=0)
    assert _ids(client, teacher_headers)[:2] == [part.id, fresh.id]
    part.reviewed_at = utcnow()
    db.add(Like(user_id=teacher.id, post_id=part.id))
    db.commit()
    ids = _ids(client, teacher_headers)
    assert ids.index(fresh.id) < ids.index(part.id)


def test_a_vetoed_participacion_is_not_pending(client, db, teacher_headers, klass, student, enrolled):
    _mk(db, student, klass, "v", type="participacion", taps=1, status="vetoed")
    assert all(p["pending_count"] is None for p in _items(client, teacher_headers))
    assert _ids(client, teacher_headers)  # still listed, just not in tier 1


def test_an_ungraded_entrega_raises_its_tarea_with_a_count(
        client, db, teacher_headers, klass, teacher, student, enrolled, student2):
    tarea = _mk(db, teacher, klass, "tarea", age_h=24 * 3, type="tarea")
    fresh = _mk(db, student2, klass, "fresh", age_h=0)
    _mk(db, student, klass, "entrega", age_h=1, parent_id=tarea.id, is_entrega=True)
    items = _items(client, teacher_headers)
    assert items[0]["id"] == tarea.id and items[0]["pending_count"] == 1
    assert [p["id"] for p in items].index(fresh.id) > 0


def test_grading_clears_it_and_a_late_entrega_brings_it_back(
        client, db, teacher_headers, klass, teacher, student, enrolled, student2):
    tarea = _mk(db, teacher, klass, "tarea", age_h=24 * 3, type="tarea")
    e = _mk(db, student, klass, "entrega", age_h=2, parent_id=tarea.id, is_entrega=True)
    db.add(Review(item_post_id=tarea.id, student_id=student.id, entrega_post_id=e.id,
                  reviewer_id=teacher.id, score=90))
    db.commit()
    assert all(p["pending_count"] is None for p in _items(client, teacher_headers))
    _mk(db, student2, klass, "tarde", age_h=0, parent_id=tarea.id, is_entrega=True)
    items = _items(client, teacher_headers)
    assert items[0]["id"] == tarea.id and items[0]["pending_count"] == 1


def test_a_review_of_a_replaced_entrega_does_not_count(
        client, db, teacher_headers, klass, teacher, student, enrolled):
    tarea = _mk(db, teacher, klass, "tarea", age_h=48, type="tarea")
    old = _mk(db, student, klass, "v1", age_h=5, parent_id=tarea.id, is_entrega=True)
    db.add(Review(item_post_id=tarea.id, student_id=student.id, entrega_post_id=old.id,
                  reviewer_id=teacher.id, score=80))
    db.commit()
    _mk(db, student, klass, "v2", age_h=1, parent_id=tarea.id, is_entrega=True)
    items = _items(client, teacher_headers)
    assert items[0]["id"] == tarea.id and items[0]["pending_count"] == 1


def test_a_ghost_entrega_is_not_pending(client, db, teacher_headers, klass, teacher, ghost):
    tarea = _mk(db, teacher, klass, "tarea", age_h=48, type="tarea")
    _mk(db, ghost, klass, "entrega", age_h=1, parent_id=tarea.id, is_entrega=True)
    assert all(p["pending_count"] is None for p in _items(client, teacher_headers))


def test_an_examen_with_an_upload_is_pending_a_paper_one_is_not(
        client, db, teacher_headers, klass, teacher, student, enrolled):
    digital = _mk(db, teacher, klass, "digital", age_h=48, type="examen")
    paper = _mk(db, teacher, klass, "paper", age_h=48, type="examen")
    answer = _mk(db, student, klass, "", age_h=1, parent_id=digital.id)
    db.add(Attachment(post_id=answer.id, file_name="a.pdf", mime_type="application/pdf",
                      file_size=10, file_key="k"))
    db.commit()
    items = {p["id"]: p for p in _items(client, teacher_headers)}
    assert items[digital.id]["pending_count"] == 1
    assert items[paper.id]["pending_count"] is None


def test_a_calificado_examen_is_not_pending(client, db, teacher_headers, klass, teacher, student, enrolled):
    ex = _mk(db, teacher, klass, "ex", age_h=48, type="examen", graded_at=utcnow())
    _mk(db, student, klass, "mi examen", age_h=1, parent_id=ex.id, is_entrega=True)
    assert all(p["pending_count"] is None for p in _items(client, teacher_headers))


def test_another_teachers_class_is_never_pending_for_me(client, db, teacher_headers, student):
    other_teacher = User(google_id="g-t2", email="t2@example.com", name="Otro", role="teacher")
    db.add(other_teacher)
    db.commit()
    other = Class(name="Otra", code="OTRA2026TIERS", teacher_id=other_teacher.id,
                  start_date=date(2026, 8, 17), end_date=date(2026, 12, 4), schedule_json=[])
    db.add(other)
    db.commit()
    db.add(Enrollment(user_id=student.id, class_id=other.id))
    db.commit()
    part = _mk(db, student, other, "part", age_h=200, type="participacion", taps=1)
    fresh = _mk(db, student, other, "fresh", age_h=0)
    ids = _ids(client, teacher_headers)
    assert ids.index(fresh.id) < ids.index(part.id)


def test_students_never_get_a_pending_count(client, db, auth_headers, klass, teacher, student, enrolled, student2):
    tarea = _mk(db, teacher, klass, "tarea", age_h=48, type="tarea")
    _mk(db, student2, klass, "entrega", age_h=1, parent_id=tarea.id, is_entrega=True)
    assert all(p["pending_count"] is None for p in _items(client, auth_headers))


def test_old_pending_still_comes_first(client, db, teacher_headers, klass, student, enrolled, student2):
    part = _mk(db, student, klass, "old part", age_h=24 * 30, type="participacion", taps=1)
    _mk(db, student2, klass, "fresh", age_h=0)
    assert _ids(client, teacher_headers)[0] == part.id


def test_paging_is_stable_while_the_teacher_validates(
        client, db, teacher_headers, klass, teacher, student, enrolled):
    ids = {_mk(db, student, klass, f"p{i}", age_h=i, type="participacion", taps=1).id
           for i in range(25)}
    seen, url = [], "/api/feed?limit=10"
    while url:
        body = client.get(url, headers=teacher_headers).json()
        page = [p["id"] for p in body["items"]]
        seen += page
        for pid in page:  # validate everything just seen
            db.get(Post, pid).reviewed_at = utcnow()
            db.add(Like(user_id=teacher.id, post_id=pid))
        db.commit()
        url = f"/api/feed?limit=10&cursor={body['next_cursor']}" if body["next_cursor"] else None
    assert len(seen) == len(set(seen)) and set(seen) == ids
