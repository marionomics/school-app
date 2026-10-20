import pytest

from app import storage
from app.models import Attachment, Post


@pytest.fixture()
def r2(monkeypatch):
    """R2 'configured', uploads recorded, links predictable — no network."""
    uploads = []
    monkeypatch.setattr(storage, "is_r2_configured", lambda: True)
    monkeypatch.setattr(storage, "upload_bytes",
                        lambda data, key, content_type: uploads.append((key, content_type)))
    monkeypatch.setattr(storage, "generate_presigned_url",
                        lambda key, expires=3600: f"https://r2.test/{key}?exp={expires}")
    return uploads


def _post_with(db, author, klass, *atts, status="active"):
    p = Post(author_id=author.id, class_id=klass.id, content="mira", status=status)
    db.add(p)
    db.flush()
    for i, (name, mime) in enumerate(atts):
        db.add(Attachment(post_id=p.id, file_key=f"posts/{p.id}_{i}", file_name=name,
                          file_size=10, mime_type=mime))
    db.commit()
    return p


def _feed_post(client, headers, pid):
    items = client.get("/api/feed", headers=headers).json()["items"]
    return next(p for p in items if p["id"] == pid)


def test_an_image_attachment_carries_a_one_hour_url_and_a_pdf_does_not(
        client, db, auth_headers, student, klass, enrolled, r2):
    p = _post_with(db, student, klass, ("foto.jpg", "image/jpeg"), ("tarea.pdf", "application/pdf"))
    atts = _feed_post(client, auth_headers, p.id)["attachments"]
    by_name = {a["file_name"]: a for a in atts}
    assert by_name["foto.jpg"]["url"] == f"https://r2.test/posts/{p.id}_0?exp=3600"
    assert by_name["tarea.pdf"]["url"] is None


def test_heic_and_svg_get_no_url(client, db, auth_headers, student, klass, enrolled, r2):
    p = _post_with(db, student, klass, ("a.heic", "image/heic"), ("b.svg", "image/svg+xml"),
                   ("c.png", "image/png"), ("d.webp", "image/webp"), ("e.gif", "image/gif"))
    urls = {a["file_name"]: a["url"] for a in _feed_post(client, auth_headers, p.id)["attachments"]}
    assert urls["a.heic"] is None and urls["b.svg"] is None
    assert all(urls[n] for n in ("c.png", "d.webp", "e.gif"))


def test_no_r2_means_no_url(client, db, auth_headers, student, klass, enrolled, monkeypatch):
    monkeypatch.setattr(storage, "is_r2_configured", lambda: False)
    p = _post_with(db, student, klass, ("foto.jpg", "image/jpeg"))
    assert _feed_post(client, auth_headers, p.id)["attachments"][0]["url"] is None


def test_deleted_post_sends_no_photos(client, db, auth_headers, student, klass, enrolled, r2):
    p = _post_with(db, student, klass, ("foto.jpg", "image/jpeg"))
    reply = Post(author_id=student.id, class_id=klass.id, parent_id=p.id, content="r")
    db.add(reply)
    db.commit()
    p.reply_count = 1        # a deleted root with replies still opens as a thread
    p.status = "deleted"
    db.commit()
    thread = client.get(f"/api/posts/{p.id}", headers=auth_headers).json()
    assert thread["post"]["attachments"] == []


def test_a_vetoed_post_keeps_its_photos(client, db, auth_headers, student, klass, enrolled, r2):
    p = _post_with(db, student, klass, ("foto.jpg", "image/jpeg"), status="vetoed")
    atts = _feed_post(client, auth_headers, p.id)["attachments"]
    assert atts[0]["url"]


def test_the_exam_roster_carries_the_url(client, db, teacher, teacher_headers, student,
                                         klass, enrolled, r2):
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen", content="P1",
             examen_mode="paper")
    db.add(x)
    db.commit()
    reply = Post(author_id=student.id, class_id=klass.id, parent_id=x.id, content="mis respuestas")
    db.add(reply)
    db.flush()
    db.add(Attachment(post_id=reply.id, file_key="posts/x", file_name="hoja.jpg",
                      file_size=10, mime_type="image/jpeg"))
    db.commit()
    rows = client.get(f"/api/review/examenes/{x.id}", headers=teacher_headers).json()["rows"]
    row = next(r for r in rows if r["student"]["id"] == student.id)
    assert row["submission"]["attachments"][0]["url"] == "https://r2.test/posts/x?exp=3600"


def test_presigned_url_error_degrades_gracefully(client, db, auth_headers, student, klass,
                                                  enrolled, monkeypatch):
    """If presigned URL generation fails, the photo degrades to a chip (url: None)
    and the feed still returns 200."""
    monkeypatch.setattr(storage, "is_r2_configured", lambda: True)
    def raise_error(key, expires=3600):
        raise Exception("R2 connection failed")
    monkeypatch.setattr(storage, "generate_presigned_url", raise_error)
    p = _post_with(db, student, klass, ("foto.jpg", "image/jpeg"))
    response = client.get("/api/feed", headers=auth_headers)
    assert response.status_code == 200
    atts = _feed_post(client, auth_headers, p.id)["attachments"]
    assert atts[0]["url"] is None
    assert atts[0]["file_name"] == "foto.jpg"
