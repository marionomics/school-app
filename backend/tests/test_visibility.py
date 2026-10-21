from datetime import date

from app.models import Class, Enrollment, Post
from app.services.visibility import assignment_visible, root_visible, viewer_class_ids


def _other_class(db, teacher):
    k = Class(name="Macro", code="MACROVIS", teacher_id=teacher.id,
              start_date=date(2026, 8, 17), end_date=date(2026, 12, 4), schedule_json=[])
    db.add(k)
    db.commit()
    return k


def test_viewer_class_ids_are_enrollments_of_any_status_plus_classes_taught(
        db, student, teacher, klass, ghost):
    other = _other_class(db, teacher)
    db.add(Enrollment(user_id=student.id, class_id=other.id, status="ghost"))
    db.commit()
    assert set(viewer_class_ids(db, student)) == {other.id}
    assert set(viewer_class_ids(db, teacher)) == {klass.id, other.id}
    assert set(viewer_class_ids(db, ghost)) == {klass.id}


def test_assignment_visible_hides_other_classes_assignments_only(db, teacher, klass, student, enrolled):
    other = _other_class(db, teacher)
    rows = [
        Post(author_id=teacher.id, class_id=klass.id, type="tarea", content="mine"),
        Post(author_id=teacher.id, class_id=other.id, type="tarea", content="theirs"),
        Post(author_id=teacher.id, class_id=other.id, type="examen", content="theirs x"),
        Post(author_id=teacher.id, class_id=other.id, type="regular", content="social"),
    ]
    db.add_all(rows)
    db.commit()
    ids = viewer_class_ids(db, student)
    seen = {p.content for p in db.query(Post).filter(assignment_visible(ids)).all()}
    assert seen == {"mine", "social"}


def test_root_visible(db, teacher, klass, student, enrolled):
    other = _other_class(db, teacher)
    ids = viewer_class_ids(db, student)
    assert root_visible(Post(type="tarea", class_id=klass.id), ids)
    assert not root_visible(Post(type="examen", class_id=other.id), ids)
    assert root_visible(Post(type="regular", class_id=other.id), ids)
