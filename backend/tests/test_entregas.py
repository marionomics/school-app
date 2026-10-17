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


def _entregar(client, headers, tarea_id, content):
    return client.post("/api/posts", data={
        "content": content, "parent_id": str(tarea_id), "is_entrega": "true",
    }, headers=headers).json()


def _thread_flags(client, headers, tarea_id):
    r = client.get(f"/api/posts/{tarea_id}", headers=headers)
    return {p["id"]: p["is_entrega"] for p in r.json()["replies"]}


def test_only_the_latest_entrega_shows_as_the_entrega(client, teacher_headers, auth_headers, klass, enrolled):
    tarea_id = _tarea(client, teacher_headers, klass)
    first = _entregar(client, auth_headers, tarea_id, "primera")
    second = _entregar(client, auth_headers, tarea_id, "segunda")
    for headers in (auth_headers, teacher_headers):
        flags = _thread_flags(client, headers, tarea_id)
        assert flags[first["id"]] is False
        assert flags[second["id"]] is True


def test_deleting_the_latest_entrega_brings_back_the_previous_one(
        db, client, teacher_headers, auth_headers, klass, enrolled, student):
    # Bug 2: entrego A → entrego B → borro B left the tarea at 0 although A was
    # still published. B stops counting (no evidence, no points); A is still
    # evidence and counts again.
    from app.services.grades import _counting_entrega

    tarea_id = _tarea(client, teacher_headers, klass)
    first = _entregar(client, auth_headers, tarea_id, "primera")
    second = _entregar(client, auth_headers, tarea_id, "segunda")
    assert client.delete(f"/api/posts/{second['id']}", headers=auth_headers).status_code == 204

    db.expire_all()
    assert _counting_entrega(db, student.id, tarea_id).id == first["id"]
    assert _thread_flags(client, teacher_headers, tarea_id)[first["id"]] is True


def test_a_plain_reply_never_becomes_the_entrega(
        db, client, teacher_headers, auth_headers, klass, enrolled, student):
    from app.services.grades import _counting_entrega

    tarea_id = _tarea(client, teacher_headers, klass)
    client.post("/api/posts", data={"content": "¿puedo entregar mañana?",
                                    "parent_id": str(tarea_id)}, headers=auth_headers)
    only = _entregar(client, auth_headers, tarea_id, "mi entrega")
    client.delete(f"/api/posts/{only['id']}", headers=auth_headers)

    db.expire_all()
    assert _counting_entrega(db, student.id, tarea_id) is None


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
