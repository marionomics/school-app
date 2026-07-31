from app.models import Post


def _tarea(client, teacher_headers, klass):
    r = client.post("/api/posts", data={
        "content": "Tarea 1", "type": "tarea", "class_id": str(klass.id),
    }, headers=teacher_headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_reply_can_be_marked_as_entrega(client, teacher_headers, auth_headers, klass, enrolled):
    tarea_id = _tarea(client, teacher_headers, klass)
    r = client.post("/api/posts", data={
        "content": "Aquí está mi tarea",
        "parent_id": str(tarea_id),
        "is_entrega": "true",
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    assert r.json()["is_entrega"] is True


def test_marking_second_entrega_clears_the_first(db, client, teacher_headers, auth_headers, klass, enrolled):
    tarea_id = _tarea(client, teacher_headers, klass)
    first = client.post("/api/posts", data={
        "content": "primera", "parent_id": str(tarea_id), "is_entrega": "true",
    }, headers=auth_headers).json()
    second = client.post("/api/posts", data={
        "content": "segunda", "parent_id": str(tarea_id), "is_entrega": "true",
    }, headers=auth_headers).json()

    db.expire_all()
    assert db.get(Post, first["id"]).is_entrega is False
    assert db.get(Post, second["id"]).is_entrega is True


def test_entrega_only_on_a_tarea(client, auth_headers, klass, enrolled, student):
    plain = client.post("/api/posts", data={
        "content": "post normal", "class_id": str(klass.id),
    }, headers=auth_headers).json()
    r = client.post("/api/posts", data={
        "content": "no debería contar", "parent_id": str(plain["id"]), "is_entrega": "true",
    }, headers=auth_headers)
    assert r.status_code == 422


def test_entrega_requires_active_enrollment(db, client, teacher_headers, klass, ghost):
    # `ghost` is enrolled with status="ghost": may post, earns nothing, cannot entregar.
    from app.auth.sessions import create_session
    headers = {"Authorization": f"Bearer {create_session(db, ghost)}"}
    tarea_id = _tarea(client, teacher_headers, klass)
    r = client.post("/api/posts", data={
        "content": "soy fantasma", "parent_id": str(tarea_id), "is_entrega": "true",
    }, headers=headers)
    assert r.status_code == 403
