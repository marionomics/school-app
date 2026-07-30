from app.models import Post, PointsLedger


def test_create_regular_post(client, db, auth_headers, enrolled, klass):
    res = client.post("/api/posts", data={"content": "hola mundo"}, headers=auth_headers)
    assert res.status_code == 201
    body = res.json()
    assert body["type"] == "regular"
    assert body["class_id"] == klass.id  # only active enrollment -> auto attribution
    assert body["author"]["username"] is None or isinstance(body["author"]["username"], str)


def test_create_participacion_awards_points(client, db, auth_headers, enrolled, klass):
    res = client.post(
        "/api/posts",
        data={"content": "expliqué el modelo de oferta y demanda con un ejemplo",
              "type": "participacion", "taps": "2"},
        headers=auth_headers,
    )
    assert res.status_code == 201
    assert res.json()["taps"] == 2
    row = db.query(PointsLedger).filter_by(source_type="participacion").one()
    assert float(row.points) == 2.0


def test_participacion_requires_taps_and_class(client, auth_headers, enrolled):
    res = client.post("/api/posts", data={"content": "x", "type": "participacion"},
                      headers=auth_headers)
    assert res.status_code == 422


def test_participacion_cannot_be_reply(client, db, auth_headers, enrolled, klass, student):
    root = Post(author_id=student.id, content="root", class_id=klass.id)
    db.add(root)
    db.commit()
    res = client.post(
        "/api/posts",
        data={"content": "x", "type": "participacion", "taps": "1",
              "parent_id": str(root.id)},
        headers=auth_headers,
    )
    assert res.status_code == 422


def test_reply_depth_limit(client, db, auth_headers, enrolled, klass, student):
    p1 = Post(author_id=student.id, content="1", class_id=klass.id)
    db.add(p1)
    db.commit()
    p2 = Post(author_id=student.id, content="2", class_id=klass.id, parent_id=p1.id)
    db.add(p2)
    db.commit()
    p3 = Post(author_id=student.id, content="3", class_id=klass.id, parent_id=p2.id)
    db.add(p3)
    db.commit()
    res = client.post("/api/posts", data={"content": "4", "parent_id": str(p3.id)},
                      headers=auth_headers)
    assert res.status_code == 422


def test_reply_bumps_root_and_count(client, db, auth_headers, enrolled, klass, student):
    root = Post(author_id=student.id, content="root", class_id=klass.id)
    db.add(root)
    db.commit()
    before = root.last_activity_at
    res = client.post("/api/posts", data={"content": "re", "parent_id": str(root.id)},
                      headers=auth_headers)
    assert res.status_code == 201
    db.refresh(root)
    assert root.reply_count == 1
    assert root.last_activity_at >= before


def test_student_post_requires_enrollment_for_class(client, db, auth_headers, student, klass):
    # student NOT enrolled (no `enrolled` fixture) and sends explicit class_id
    res = client.post("/api/posts", data={"content": "x", "class_id": str(klass.id)},
                      headers=auth_headers)
    assert res.status_code == 403


def test_default_class_endpoint(client, auth_headers, enrolled, klass):
    res = client.get("/api/posts/default-class", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["class_id"] == klass.id


def test_upload_rejected_when_r2_off(client, auth_headers, enrolled):
    res = client.post(
        "/api/posts",
        data={"content": "con archivo"},
        files=[("files", ("nota.pdf", b"%PDF-1.4", "application/pdf"))],
        headers=auth_headers,
    )
    assert res.status_code == 400


def test_teacher_cannot_post_to_unowned_class(client, db, teacher_headers, klass):
    # klass is owned by the `teacher` fixture; create a second teacher who does NOT own it
    from app.auth.sessions import create_session
    from app.models import User
    other = User(google_id="g-teach2", email="teach2@example.com", name="Otro Profe", role="teacher")
    db.add(other)
    db.commit()
    headers = {"Authorization": f"Bearer {create_session(db, other)}"}
    res = client.post("/api/posts", data={"content": "hola", "class_id": str(klass.id)}, headers=headers)
    assert res.status_code == 403


def test_teacher_can_post_to_own_class(client, db, teacher_headers, klass):
    res = client.post("/api/posts", data={"content": "aviso", "class_id": str(klass.id)}, headers=teacher_headers)
    assert res.status_code == 201
    assert res.json()["class_id"] == klass.id
