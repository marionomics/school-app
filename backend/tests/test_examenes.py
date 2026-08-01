import pytest


def _make_examen(client, headers, klass, mode="paper"):
    return client.post("/api/posts", data={
        "content": "Parcial 1", "type": "examen",
        "class_id": str(klass.id), "examen_mode": mode,
    }, headers=headers)


def test_teacher_creates_a_paper_examen(client, teacher_headers, klass):
    r = _make_examen(client, teacher_headers, klass)
    assert r.status_code == 201, r.text
    assert r.json()["examen_mode"] == "paper"
    assert r.json()["graded_at"] is None


def test_examen_mode_defaults_to_paper(client, teacher_headers, klass):
    r = client.post("/api/posts", data={
        "content": "Parcial", "type": "examen", "class_id": str(klass.id),
    }, headers=teacher_headers)
    assert r.json()["examen_mode"] == "paper"


def test_invalid_examen_mode_is_rejected(client, teacher_headers, klass):
    r = _make_examen(client, teacher_headers, klass, mode="oral")
    assert r.status_code == 422


def test_student_cannot_create_an_examen(client, auth_headers, klass):
    r = _make_examen(client, auth_headers, klass)
    assert r.status_code == 403


def test_teacher_marks_and_unmarks_calificado(client, teacher_headers, klass):
    examen_id = _make_examen(client, teacher_headers, klass).json()["id"]
    r = client.post(f"/api/posts/{examen_id}/graded", headers=teacher_headers)
    assert r.status_code == 200
    assert r.json()["graded_at"] is not None
    r = client.delete(f"/api/posts/{examen_id}/graded", headers=teacher_headers)
    assert r.json()["graded_at"] is None


def test_only_a_tarea_or_examen_can_be_marked_graded(client, db, teacher_headers, auth_headers, klass, enrolled):
    post_id = client.post("/api/posts", data={"content": "hola"},
                          headers=auth_headers).json()["id"]
    r = client.post(f"/api/posts/{post_id}/graded", headers=teacher_headers)
    assert r.status_code == 422


def test_student_cannot_mark_calificado(client, teacher_headers, auth_headers, klass):
    examen_id = _make_examen(client, teacher_headers, klass).json()["id"]
    r = client.post(f"/api/posts/{examen_id}/graded", headers=auth_headers)
    assert r.status_code == 403
