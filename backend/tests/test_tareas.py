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
    r = client.post("/api/posts", data={
        "content": "tarea sin clase",
        "type": "tarea",
    }, headers=teacher_headers)
    assert r.status_code == 422
