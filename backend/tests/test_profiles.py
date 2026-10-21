from datetime import date, datetime, timedelta, timezone

from app.models import Attachment, Class, Enrollment, Post, User

T0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _name(db, user, username):
    user.username = username
    db.commit()
    return user


def _post(db, author, klass=None, at=T0, **kw):
    p = Post(author_id=author.id, class_id=klass.id if klass else None,
             content=kw.pop("content", "hola"), created_at=at, last_activity_at=at, **kw)
    db.add(p)
    db.commit()
    return p


def _other_class(db, teacher):
    k = Class(name="Macro", code="MACROPROF", teacher_id=teacher.id,
              start_date=date(2026, 8, 17), end_date=date(2026, 12, 4), schedule_json=[])
    db.add(k)
    db.commit()
    return k


# ---- header -----------------------------------------------------------------

def test_header_fields_and_is_me(client, db, student, student2, auth_headers, student2_headers,
                                 enrolled):
    _name(db, student, "ana")
    mine = client.get("/api/users/ana", headers=auth_headers).json()
    assert mine["username"] == "ana" and mine["is_me"] is True
    assert {"id", "name", "bio", "avatar_url", "role", "aura_received", "has_own_avatar"} <= set(mine)
    theirs = client.get("/api/users/ana", headers=student2_headers).json()
    assert theirs["is_me"] is False


def test_unknown_username_is_404(client, auth_headers):
    assert client.get("/api/users/nadie_aqui", headers=auth_headers).status_code == 404


def test_username_available_still_routes(client, auth_headers):
    r = client.get("/api/users/username-available?u=libre_123", headers=auth_headers)
    assert r.status_code == 200 and "available" in r.json()


def test_aura_received_counts_active_posts_only(client, db, student, auth_headers, enrolled, klass):
    _name(db, student, "ana")
    _post(db, student, klass, like_count=3)
    _post(db, student, klass, like_count=5, status="deleted")
    _post(db, student, klass, like_count=7, status="vetoed")
    assert client.get("/api/users/ana", headers=auth_headers).json()["aura_received"] == 3


# ---- grades -----------------------------------------------------------------

def test_the_owner_sees_their_grade_per_active_class(client, db, student, auth_headers, enrolled, klass):
    _name(db, student, "ana")
    grades = client.get("/api/users/ana", headers=auth_headers).json()["grades"]
    assert [g["class_id"] for g in grades] == [klass.id]
    assert grades[0]["class_name"] == "Micro"


def test_the_teacher_sees_the_same_summary_as_the_class_panel(client, db, student, teacher_headers,
                                                              enrolled, klass):
    _name(db, student, "ana")
    grades = client.get("/api/users/ana", headers=teacher_headers).json()["grades"]
    panel = client.get(f"/api/classes/{klass.id}/students/{student.id}/grade",
                       headers=teacher_headers).json()
    assert grades[0]["summary"]["total"] == panel["total"]
    assert grades[0]["summary"].keys() == panel.keys()


def test_a_classmate_gets_no_grades_key(client, db, student, student2_headers, enrolled):
    _name(db, student, "ana")
    assert "grades" not in client.get("/api/users/ana", headers=student2_headers).json()


def test_another_teacher_gets_no_grades_key(client, db, student, enrolled):
    from app.auth.sessions import create_session

    other = User(google_id="g-other-prof", email="op@example.com", name="Otra", role="teacher")
    db.add(other)
    db.commit()
    _name(db, student, "ana")
    headers = {"Authorization": f"Bearer {create_session(db, other)}"}
    assert "grades" not in client.get("/api/users/ana", headers=headers).json()


def test_a_teacher_sees_only_the_classes_they_teach(client, db, student, teacher_headers,
                                                    enrolled, klass):
    from app.auth.sessions import create_session

    b = User(google_id="g-prof-b", email="pb@example.com", name="Profe B", role="teacher")
    db.add(b)
    db.commit()
    kb = Class(name="Macro B", code="MACROB1234", teacher_id=b.id,
               start_date=date(2026, 8, 17), end_date=date(2026, 12, 4), schedule_json=[])
    db.add(kb)
    db.commit()
    db.add(Enrollment(user_id=student.id, class_id=kb.id))
    db.commit()
    _name(db, student, "ana")
    a_view = client.get("/api/users/ana", headers=teacher_headers).json()["grades"]
    assert [g["class_id"] for g in a_view] == [klass.id]
    b_headers = {"Authorization": f"Bearer {create_session(db, b)}"}
    b_view = client.get("/api/users/ana", headers=b_headers).json()["grades"]
    assert [g["class_id"] for g in b_view] == [kb.id]


def test_the_owner_does_not_see_a_ghost_class(client, db, teacher, student, auth_headers,
                                              enrolled, klass):
    _name(db, student, "ana")
    old = _other_class(db, teacher)
    db.add(Enrollment(user_id=student.id, class_id=old.id, status="ghost"))
    db.commit()
    grades = client.get("/api/users/ana", headers=auth_headers).json()["grades"]
    assert [g["class_id"] for g in grades] == [klass.id]


def test_username_lookup_is_case_insensitive(client, db, student, auth_headers):
    _name(db, student, "ana")
    assert client.get("/api/users/ANA", headers=auth_headers).status_code == 200


def test_a_teacher_viewing_their_own_profile_gets_an_empty_grades_list(client, db, teacher,
                                                                       teacher_headers, klass):
    _name(db, teacher, "profe")
    body = client.get("/api/users/profe", headers=teacher_headers).json()
    assert body["is_me"] is True and body["grades"] == []


# ---- posts tab ----------------------------------------------------------------

def test_posts_tab_top_level_newest_first_no_deleted(client, db, student, auth_headers, enrolled, klass):
    _name(db, student, "ana")
    old = _post(db, student, klass, at=T0, content="viejo")
    new = _post(db, student, klass, at=T0 + timedelta(hours=1), content="nuevo")
    _post(db, student, klass, at=T0 + timedelta(hours=2), status="deleted")
    vet = _post(db, student, klass, at=T0 + timedelta(hours=3), status="vetoed")
    _post(db, student, klass, at=T0 + timedelta(hours=4), parent_id=old.id)  # a reply
    items = client.get("/api/users/ana/posts?tab=posts", headers=auth_headers).json()["items"]
    assert [p["id"] for p in items] == [vet.id, new.id, old.id]


def test_posts_tab_paginates(client, db, student, auth_headers, enrolled, klass):
    _name(db, student, "ana")
    ids = [_post(db, student, klass, at=T0 + timedelta(minutes=i)).id for i in range(3)]
    r1 = client.get("/api/users/ana/posts?tab=posts&limit=2", headers=auth_headers).json()
    assert [p["id"] for p in r1["items"]] == [ids[2], ids[1]] and r1["next_cursor"]
    r2 = client.get(f"/api/users/ana/posts?tab=posts&limit=2&cursor={r1['next_cursor']}",
                    headers=auth_headers).json()
    assert [p["id"] for p in r2["items"]] == [ids[0]] and r2["next_cursor"] is None


# ---- replies tab ----------------------------------------------------------------

def test_replies_tab_excludes_entregas_and_carries_the_parent(client, db, student, student2,
                                                              teacher, auth_headers, enrolled, klass):
    _name(db, student, "ana")
    _name(db, student2, "beto")
    root = _post(db, student2, klass, content="El modelo de oferta y demanda explica " * 10)
    reply = _post(db, student, klass, at=T0 + timedelta(minutes=1), parent_id=root.id)
    tarea = _post(db, teacher, klass, type="tarea", content="Cap 3")
    _post(db, student, klass, at=T0 + timedelta(minutes=2), parent_id=tarea.id, is_entrega=True)
    items = client.get("/api/users/ana/posts?tab=replies", headers=auth_headers).json()["items"]
    assert [p["id"] for p in items] == [reply.id]
    assert items[0]["parent"]["id"] == root.id
    assert items[0]["parent"]["author_username"] == "beto"
    assert len(items[0]["parent"]["excerpt"]) == 120


def test_a_reply_to_a_deleted_post_has_an_empty_excerpt(client, db, student, student2, auth_headers,
                                                        enrolled, klass):
    _name(db, student, "ana")
    root = _post(db, student2, klass, status="deleted", content="se fue")
    _post(db, student, klass, at=T0 + timedelta(minutes=1), parent_id=root.id)
    items = client.get("/api/users/ana/posts?tab=replies", headers=auth_headers).json()["items"]
    assert items[0]["parent"]["excerpt"] == ""


def _with_file(db, post):
    db.add(Attachment(post_id=post.id, file_key=f"posts/{post.id}", file_name="hoja.jpg",
                      file_size=1, mime_type="image/jpeg"))
    db.commit()
    return post


def test_a_reply_with_files_to_an_examen_or_tarea_is_a_submission_and_hidden(
        client, db, teacher, student, student2, auth_headers, enrolled, klass):
    # Examen answers are rarely flagged is_entrega; the roster counts the
    # latest reply with files as the submission, so the profile must too.
    _name(db, student2, "beto")
    examen = _post(db, teacher, klass, type="examen", content="P1")
    tarea = _post(db, teacher, klass, type="tarea", content="Cap 4")
    _with_file(db, _post(db, student2, klass, at=T0 + timedelta(minutes=1), parent_id=examen.id))
    _with_file(db, _post(db, student2, klass, at=T0 + timedelta(minutes=2), parent_id=tarea.id))
    question = _post(db, student2, klass, at=T0 + timedelta(minutes=3), parent_id=examen.id,
                     content="¿Cuánto tiempo tenemos?")
    items = client.get("/api/users/beto/posts?tab=replies", headers=auth_headers).json()["items"]
    assert [p["id"] for p in items] == [question.id]


def test_a_reply_to_a_submission_has_an_empty_excerpt(client, db, teacher, student, student2,
                                                      auth_headers, enrolled, klass):
    _name(db, student, "ana")
    _name(db, student2, "beto")
    tarea = _post(db, teacher, klass, type="tarea", content="Cap 3")
    entrega = _post(db, student2, klass, at=T0 + timedelta(minutes=1), parent_id=tarea.id,
                    is_entrega=True, content="Mi tarea completa")
    examen = _post(db, teacher, klass, type="examen", content="P1")
    answer = _with_file(db, _post(db, student2, klass, at=T0 + timedelta(minutes=2),
                                  parent_id=examen.id, content="Mi respuesta"))
    _post(db, student, klass, at=T0 + timedelta(minutes=3), parent_id=entrega.id, content="bien")
    _post(db, student, klass, at=T0 + timedelta(minutes=4), parent_id=answer.id, content="ok")
    items = client.get("/api/users/ana/posts?tab=replies", headers=auth_headers).json()["items"]
    assert [p["parent"]["id"] for p in items] == [answer.id, entrega.id]
    assert [p["parent"]["excerpt"] for p in items] == ["", ""]


def test_a_reply_to_a_vetoed_post_keeps_its_excerpt(client, db, student, student2, auth_headers,
                                                    enrolled, klass):
    _name(db, student, "ana")
    root = _post(db, student2, klass, status="vetoed", content="sigue visible")
    _post(db, student, klass, at=T0 + timedelta(minutes=1), parent_id=root.id)
    items = client.get("/api/users/ana/posts?tab=replies", headers=auth_headers).json()["items"]
    assert items[0]["parent"]["excerpt"] == "sigue visible"


# ---- scoping ----------------------------------------------------------------

def test_a_student_never_sees_another_class_assignment_on_the_teachers_profile(
        client, db, teacher, student, auth_headers, enrolled, klass):
    _name(db, teacher, "profe")
    other = _other_class(db, teacher)
    mine = _post(db, teacher, klass, type="tarea", content="de mi clase")
    _post(db, teacher, other, type="tarea", content="de otra clase", at=T0 + timedelta(minutes=1))
    _post(db, teacher, other, type="examen", content="examen ajeno", at=T0 + timedelta(minutes=2))
    items = client.get("/api/users/profe/posts?tab=posts", headers=auth_headers).json()["items"]
    assert [p["id"] for p in items] == [mine.id]


def test_a_reply_inside_another_class_examen_is_hidden(client, db, teacher, student, student2,
                                                       auth_headers, enrolled, klass):
    _name(db, student2, "beto")
    other = _other_class(db, teacher)
    db.add(Enrollment(user_id=student2.id, class_id=other.id))
    db.commit()
    x = _post(db, teacher, other, type="examen", content="P1 ajeno")
    _post(db, student2, other, at=T0 + timedelta(minutes=1), parent_id=x.id, content="respuesta")
    visible = _post(db, student2, klass, at=T0 + timedelta(minutes=2), content="hilo social")
    ok = _post(db, student2, klass, at=T0 + timedelta(minutes=3), parent_id=visible.id)
    items = client.get("/api/users/beto/posts?tab=replies", headers=auth_headers).json()["items"]
    assert [p["id"] for p in items] == [ok.id]


def test_replies_paging_survives_filtered_rows(client, db, teacher, student, student2,
                                               auth_headers, enrolled, klass):
    # The newest reply is filtered out by scoping; the page must still offer
    # a cursor so the older visible reply is reachable.
    _name(db, student2, "beto")
    other = _other_class(db, teacher)
    db.add(Enrollment(user_id=student2.id, class_id=other.id))
    db.commit()
    social = _post(db, student2, klass, content="social")
    older = _post(db, student2, klass, at=T0 + timedelta(minutes=1), parent_id=social.id)
    x = _post(db, teacher, other, type="examen", content="ajeno")
    _post(db, student2, other, at=T0 + timedelta(minutes=2), parent_id=x.id)
    r1 = client.get("/api/users/beto/posts?tab=replies&limit=1", headers=auth_headers).json()
    assert r1["items"] == [] and r1["next_cursor"]
    r2 = client.get(f"/api/users/beto/posts?tab=replies&limit=1&cursor={r1['next_cursor']}",
                    headers=auth_headers).json()
    assert [p["id"] for p in r2["items"]] == [older.id]


def test_bad_tab_is_422(client, db, student, auth_headers):
    _name(db, student, "ana")
    assert client.get("/api/users/ana/posts?tab=likes", headers=auth_headers).status_code == 422
