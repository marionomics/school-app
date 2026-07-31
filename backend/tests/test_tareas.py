from datetime import datetime, timedelta, timezone

from app.services.dates import next_sunday_due


def test_next_sunday_from_wednesday():
    # Wed 2026-08-05 10:00 UTC -> Sunday 2026-08-09 23:59 local
    now = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)
    due = next_sunday_due(now, "America/Mexico_City")
    local = due.astimezone(timezone.utc)
    assert local > now
    assert (local - now) < timedelta(days=7)


def test_next_sunday_from_sunday_skips_to_following_week():
    # Sunday 2026-08-09 12:00 UTC must NOT return the same day
    now = datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc)
    due = next_sunday_due(now, "America/Mexico_City")
    assert (due - now) > timedelta(days=5)


def test_teacher_creates_tarea(client, teacher_headers, klass):
    r = client.post("/api/posts", data={
        "content": "Lee el capítulo 3 y resume",
        "type": "tarea",
        "class_id": str(klass.id),
    }, headers=teacher_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["type"] == "tarea"
    assert body["due_date"] is not None


def test_teacher_creates_tarea_with_explicit_due_date(client, teacher_headers, klass):
    due = datetime(2026, 9, 1, 23, 59, tzinfo=timezone.utc)
    r = client.post("/api/posts", data={
        "content": "Entrega el proyecto",
        "type": "tarea",
        "class_id": str(klass.id),
        "due_date": due.isoformat(),
    }, headers=teacher_headers)
    assert r.status_code == 201, r.text
    assert r.json()["due_date"].startswith("2026-09-01")


def test_student_cannot_create_tarea(client, auth_headers, klass):
    r = client.post("/api/posts", data={
        "content": "intento de tarea",
        "type": "tarea",
        "class_id": str(klass.id),
    }, headers=auth_headers)
    assert r.status_code == 403


def test_tarea_requires_class(client, teacher_headers):
    # teacher with no classes at all: nothing to fall back to
    r = client.post("/api/posts", data={
        "content": "tarea sin clase",
        "type": "tarea",
    }, headers=teacher_headers)
    assert r.status_code == 422


def test_teacher_tarea_falls_back_to_their_only_class(client, teacher_headers, klass):
    """The teacher owns the class but is never *enrolled* in it — attribution
    has to look at classes taught, or the composer can't post a tarea at all."""
    r = client.post("/api/posts", data={
        "content": "tarea sin class_id explícito",
        "type": "tarea",
    }, headers=teacher_headers)
    assert r.status_code == 201, r.text
    assert r.json()["class_id"] == klass.id


def test_default_class_for_teacher_is_their_class(client, teacher_headers, klass):
    r = client.get("/api/posts/default-class", headers=teacher_headers)
    assert r.status_code == 200
    assert r.json()["class_id"] == klass.id


def test_default_class_ambiguous_for_teacher_with_two_classes(
    client, db, teacher, teacher_headers, klass
):
    from datetime import date

    from app.models import Class

    other = Class(
        name="Macro", code="MACRO2026TEST", teacher_id=teacher.id,
        start_date=date(2026, 8, 17), end_date=date(2026, 12, 4),
        schedule_json=[],
    )
    db.add(other)
    # No schedule on either class: otherwise this test would pass or fail
    # depending on the wall clock when CI happens to run.
    klass.schedule_json = []
    db.commit()
    r = client.get("/api/posts/default-class", headers=teacher_headers)
    assert r.json()["class_id"] is None
