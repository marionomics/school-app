import pytest

from app import storage
from app.models import Attachment, Post


@pytest.fixture()
def r2_on(monkeypatch):
    """Pretend R2 is configured and swallow the upload — no network in tests."""
    uploaded = []
    monkeypatch.setattr(storage, "is_r2_configured", lambda: True)
    monkeypatch.setattr(
        storage,
        "upload_bytes",
        lambda data, key, content_type: uploaded.append((key, len(data))),
    )
    return uploaded


def a_file(name="nota.pdf", size=64, mime="application/pdf"):
    return ("files", (name, b"x" * size, mime))


@pytest.fixture()
def tarea(db, teacher, klass):
    t = Post(author_id=teacher.id, content="Lee el capítulo 3", type="tarea",
             class_id=klass.id)
    db.add(t)
    db.commit()
    return t


def test_reply_with_only_a_file_is_accepted(client, db, auth_headers, enrolled,
                                            klass, student, r2_on):
    root = Post(author_id=student.id, content="hilo", class_id=klass.id)
    db.add(root)
    db.commit()

    res = client.post(
        "/api/posts",
        data={"content": "", "parent_id": str(root.id)},
        files=[a_file("foto.jpg", mime="image/jpeg")],
        headers=auth_headers,
    )

    assert res.status_code == 201
    assert res.json()["attachments"][0]["file_name"] == "foto.jpg"
    assert db.query(Attachment).count() == 1
    assert len(r2_on) == 1  # the bytes actually went to storage


def test_entrega_can_be_a_photo_with_no_text(client, db, auth_headers, enrolled,
                                             tarea, r2_on):
    res = client.post(
        "/api/posts",
        data={"content": "", "parent_id": str(tarea.id), "is_entrega": "true"},
        files=[a_file("mi-tarea.jpg", mime="image/jpeg")],
        headers=auth_headers,
    )

    assert res.status_code == 201
    body = res.json()
    assert body["is_entrega"] is True
    assert len(body["attachments"]) == 1


def test_fifth_file_is_rejected(client, auth_headers, enrolled, r2_on):
    res = client.post(
        "/api/posts",
        data={"content": "cinco"},
        files=[a_file(f"{n}.pdf") for n in "abcde"],
        headers=auth_headers,
    )

    assert res.status_code == 422
    assert "4" in res.json()["detail"]


def test_oversized_file_is_rejected(client, auth_headers, enrolled, r2_on):
    res = client.post(
        "/api/posts",
        data={"content": "pesada"},
        files=[a_file("enorme.pdf", size=storage.MAX_FILE_SIZE + 1)],
        headers=auth_headers,
    )

    assert res.status_code == 422
    assert "grande" in res.json()["detail"].lower()


def test_disallowed_extension_is_rejected(client, db, auth_headers, enrolled, r2_on):
    res = client.post(
        "/api/posts",
        data={"content": "sospechoso"},
        files=[a_file("virus.exe", mime="application/octet-stream")],
        headers=auth_headers,
    )

    assert res.status_code == 422
    assert "permitido" in res.json()["detail"].lower()
    assert db.query(Attachment).count() == 0
