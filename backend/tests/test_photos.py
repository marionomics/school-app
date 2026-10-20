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


def test_an_image_attachment_carries_a_signed_url_and_a_pdf_does_not(
        client, db, auth_headers, student, klass, enrolled, r2):
    p = _post_with(db, student, klass, ("foto.jpg", "image/jpeg"), ("tarea.pdf", "application/pdf"))
    atts = _feed_post(client, auth_headers, p.id)["attachments"]
    by_name = {a["file_name"]: a for a in atts}
    assert by_name["foto.jpg"]["url"] == f"https://r2.test/posts/{p.id}_0?exp=7200"
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
    assert row["submission"]["attachments"][0]["url"] == "https://r2.test/posts/x?exp=7200"


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


def _upload(client, headers, name="yo.jpg", mime="image/jpeg", size=100):
    return client.put("/api/users/me/avatar",
                      files={"file": (name, b"x" * size, mime)}, headers=headers)


def test_uploading_a_photo_shows_it_everywhere(client, db, auth_headers, teacher_headers,
                                               student, klass, enrolled, r2):
    student.avatar_url = "https://google.test/me.jpg"
    db.commit()
    r = _upload(client, auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["has_own_avatar"] is True
    signed = r.json()["avatar_url"]
    assert signed.startswith("https://r2.test/avatars/") and "exp=7200" in signed
    assert r2[-1][1] == "image/jpeg"

    assert client.get("/api/auth/me", headers=auth_headers).json()["avatar_url"] == signed
    pid = client.post("/api/posts", data={"content": "hola"}, headers=auth_headers).json()["id"]
    assert _feed_post(client, auth_headers, pid)["author"]["avatar_url"] == signed
    members = client.get(f"/api/classes/{klass.id}", headers=teacher_headers).json()["members"]
    assert next(m for m in members if m["id"] == student.id)["avatar_url"] == signed
    roster = client.get(f"/api/classes/{klass.id}/roster", headers=teacher_headers).json()["students"]
    assert next(s for s in roster if s["id"] == student.id)["avatar_url"] == signed


def test_removing_your_photo_goes_back_to_google(client, db, auth_headers, student, r2):
    student.avatar_url = "https://google.test/me.jpg"
    db.commit()
    _upload(client, auth_headers)
    r = client.delete("/api/users/me/avatar", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["avatar_url"] == "https://google.test/me.jpg"
    assert r.json()["has_own_avatar"] is False


def test_only_photo_formats_up_to_10mb(client, auth_headers, r2):
    assert _upload(client, auth_headers, "cv.pdf", "application/pdf").status_code == 422
    assert _upload(client, auth_headers, "a.gif", "image/gif").status_code == 422
    assert _upload(client, auth_headers, size=10 * 1024 * 1024 + 1).status_code == 422
    for name, mime in (("a.png", "image/png"), ("a.webp", "image/webp")):
        assert _upload(client, auth_headers, name, mime).status_code == 200


def test_no_r2_means_no_avatar_upload(client, auth_headers, monkeypatch):
    monkeypatch.setattr(storage, "is_r2_configured", lambda: False)
    assert _upload(client, auth_headers).status_code == 400


def test_a_student_cannot_remove_another_students_photo(client, student, student2_headers,
                                                       enrolled, r2):
    assert client.delete(f"/api/users/{student.id}/avatar",
                         headers=student2_headers).status_code == 403


def test_the_teacher_removes_a_photo_in_their_class(client, db, auth_headers, teacher_headers,
                                                   student, enrolled, r2):
    student.avatar_url = "https://google.test/me.jpg"
    db.commit()
    _upload(client, auth_headers)
    r = client.delete(f"/api/users/{student.id}/avatar", headers=teacher_headers)
    assert r.status_code == 200
    db.refresh(student)
    assert student.avatar_key is None


def test_teacher_cannot_remove_a_strangers_photo(client, db, teacher_headers, r2):
    from app.models import User

    stranger = User(google_id="g-stranger", email="x@example.com", name="X")
    db.add(stranger)
    db.commit()
    assert client.delete(f"/api/users/{stranger.id}/avatar",
                         headers=teacher_headers).status_code == 403


def test_a_storage_error_falls_back_to_the_google_photo(client, db, auth_headers, student,
                                                       r2, monkeypatch):
    student.avatar_url = "https://google.test/me.jpg"
    student.avatar_key = "avatars/1_1.jpg"
    db.commit()

    def boom(key, expires=3600):
        raise RuntimeError("r2 down")

    monkeypatch.setattr(storage, "generate_presigned_url", boom)
    r = client.get("/api/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["avatar_url"] == "https://google.test/me.jpg"


# --- F1: stable signed URLs -------------------------------------------------

@pytest.fixture()
def r2_counting(monkeypatch, r2):
    """Like r2, but every signature is a different string — so two equal URLs
    can only come from the cache."""
    calls = []

    def sign(key, expires=3600):
        calls.append(key)
        return f"https://r2.test/{key}?exp={expires}&sig={len(calls)}"

    monkeypatch.setattr(storage, "generate_presigned_url", sign)
    return calls


def test_two_feed_loads_hand_out_the_same_url(client, db, auth_headers, student, klass,
                                             enrolled, r2_counting):
    p = _post_with(db, student, klass, ("foto.jpg", "image/jpeg"))
    first = _feed_post(client, auth_headers, p.id)["attachments"][0]["url"]
    second = _feed_post(client, auth_headers, p.id)["attachments"][0]["url"]
    assert first == second
    assert "exp=7200" in first
    assert r2_counting.count(f"posts/{p.id}_0") == 1


def test_the_avatar_url_is_stable_across_requests(client, db, auth_headers, student,
                                                  r2_counting):
    student.avatar_key = "avatars/1_1.jpg"
    db.commit()
    a = client.get("/api/auth/me", headers=auth_headers).json()["avatar_url"]
    b = client.get("/api/auth/me", headers=auth_headers).json()["avatar_url"]
    assert a == b


def test_after_the_reuse_window_a_new_url_is_signed(client, db, auth_headers, student, klass,
                                                    enrolled, r2_counting, monkeypatch):
    from app.services import media

    clock = [1000.0]
    monkeypatch.setattr(media, "_now", lambda: clock[0])
    p = _post_with(db, student, klass, ("foto.jpg", "image/jpeg"))
    first = _feed_post(client, auth_headers, p.id)["attachments"][0]["url"]
    clock[0] += media.REUSE_SECONDS - 1
    assert _feed_post(client, auth_headers, p.id)["attachments"][0]["url"] == first
    clock[0] += 2
    later = _feed_post(client, auth_headers, p.id)["attachments"][0]["url"]
    assert later != first and "exp=7200" in later


def test_the_cache_is_pruned_when_it_grows(monkeypatch, r2_counting):
    from app.services import media

    for i in range(media.MAX_CACHED + 10):
        media._signed(f"k/{i}")
    assert len(media._cache) <= media.MAX_CACHED


def test_uploaded_objects_are_cached_forever_by_the_browser(monkeypatch):
    """Keys are unique per upload, so a stored object never changes."""
    puts = []

    class FakeClient:
        def put_object(self, **kw):
            puts.append(kw)

    monkeypatch.setattr(storage, "_client", lambda: FakeClient())
    storage.upload_bytes(b"x", "posts/1_a.jpg", "image/jpeg")
    assert puts[0]["CacheControl"] == "private, max-age=31536000, immutable"
    assert puts[0]["ContentType"] == "image/jpeg"


# --- F4: a vetoed post's links stay refreshable ----------------------------

def test_a_vetoed_posts_photo_link_can_be_refreshed(client, db, auth_headers, student, klass,
                                                    enrolled, r2):
    p = _post_with(db, student, klass, ("foto.jpg", "image/jpeg"), status="vetoed")
    att = db.query(Attachment).filter_by(post_id=p.id).one()
    r = client.get(f"/api/attachments/{att.id}/url", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["url"]


def test_a_deleted_posts_photo_link_is_gone(client, db, auth_headers, student, klass,
                                            enrolled, r2):
    p = _post_with(db, student, klass, ("foto.jpg", "image/jpeg"), status="deleted")
    att = db.query(Attachment).filter_by(post_id=p.id).one()
    assert client.get(f"/api/attachments/{att.id}/url",
                      headers=auth_headers).status_code == 404


# --- F5: the roster says who has their own photo ---------------------------

def test_the_roster_says_who_has_their_own_photo(client, db, auth_headers, teacher_headers,
                                                student, student2, klass, enrolled, r2):
    _upload(client, auth_headers)
    roster = client.get(f"/api/classes/{klass.id}/roster",
                        headers=teacher_headers).json()["students"]
    by_id = {s["id"]: s for s in roster}
    assert by_id[student.id]["has_own_avatar"] is True
    assert by_id[student2.id]["has_own_avatar"] is False
