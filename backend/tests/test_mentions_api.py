from datetime import datetime, timezone

from app.auth.sessions import create_session
from app.models import Class, Enrollment, Post, PostMention, User

DUE = datetime(2030, 8, 9, 23, 59, tzinfo=timezone.utc)


def _user(db, klass, handle, name=None, status="active"):
    u = User(google_id=f"g-{handle}", email=f"{handle}@example.com",
             name=name or handle.title(), username=handle)
    db.add(u)
    db.flush()
    if klass is not None:
        db.add(Enrollment(user_id=u.id, class_id=klass.id, status=status))
    db.commit()
    return u


def _h(db, u):
    return {"Authorization": f"Bearer {create_session(db, u)}"}


def _search(client, db, viewer, q):
    r = client.get("/api/users/search", params={"q": q}, headers=_h(db, viewer))
    assert r.status_code == 200, r.text
    return [u["username"] for u in r.json()["users"]]


def test_search_puts_classmates_first_and_never_the_viewer(client, db, klass):
    me = _user(db, klass, "ana")
    _user(db, None, "andres")             # not a classmate
    _user(db, klass, "anahi")
    assert _search(client, db, me, "an") == ["anahi", "andres"]


def test_search_matches_name_prefix_and_strips_the_at(client, db, klass):
    me = _user(db, klass, "ana")
    _user(db, klass, "pl", name="Pedro López")
    assert _search(client, db, me, "@ped") == ["pl"]


def test_search_treats_underscore_literally(client, db, klass):
    me = _user(db, klass, "ana")
    _user(db, klass, "a_b")
    _user(db, klass, "axb")
    assert _search(client, db, me, "a_") == ["a_b"]


def test_search_caps_at_eight(client, db, klass):
    me = _user(db, klass, "zz_me")
    for i in range(10):
        _user(db, klass, f"bea{i}")
    assert len(_search(client, db, me, "bea")) == 8


def test_team_check_reports_each_reason(client, db, teacher, klass):
    ana, pedro, luis, eva = (_user(db, klass, n) for n in ("ana", "pedro", "luis", "eva"))
    _user(db, None, "fuera")
    t = Post(author_id=teacher.id, class_id=klass.id, type="tarea", content="T", due_date=DUE)
    db.add(t)
    db.flush()
    other = Post(author_id=luis.id, class_id=klass.id, parent_id=t.id, content="@eva",
                 is_entrega=True)
    db.add(other)
    db.flush()
    db.add(PostMention(post_id=other.id, user_id=eva.id, kind="team"))
    db.commit()
    r = client.get(f"/api/posts/{t.id}/team-check",
                   params=[("u", "Pedro"), ("u", "eva"), ("u", "fuera"), ("u", "ana"),
                           ("u", "nadie_aqui")],
                   headers=_h(db, ana))
    assert r.status_code == 200, r.text
    assert r.json()["results"] == [
        {"username": "pedro", "status": "ok", "team_author": None},
        {"username": "eva", "status": "on_team", "team_author": "luis"},
        {"username": "fuera", "status": "not_in_class", "team_author": None},
        {"username": "ana", "status": "self", "team_author": None},
        {"username": "nadie_aqui", "status": "unknown", "team_author": None},
    ]


def test_team_check_needs_a_tarea_or_examen(client, db, klass):
    ana = _user(db, klass, "ana")
    p = Post(author_id=ana.id, class_id=klass.id, content="hola")
    db.add(p)
    db.commit()
    r = client.get(f"/api/posts/{p.id}/team-check", params={"u": "x_y"}, headers=_h(db, ana))
    assert r.status_code == 422


def test_team_check_denies_access_outside_viewer_classes(client, db, klass):
    """A tarea in a class the viewer is not enrolled in — 404 to avoid
    leaking enrollment and team information across class boundaries."""
    # Create a second class with a tarea
    other_teacher = _user(db, None, "otro_prof")
    other_teacher.role = "teacher"
    db.commit()
    other_klass = Class(name="Otra", code="OTRA1", teacher_id=other_teacher.id,
                        start_date=klass.start_date, end_date=klass.end_date)
    db.add(other_klass)
    db.flush()

    # Create a student who is NOT in the second class
    viewer = _user(db, klass, "viewer")

    # Create a tarea in the other class
    tarea = Post(author_id=other_teacher.id, class_id=other_klass.id,
                 type="tarea", content="T", due_date=DUE)
    db.add(tarea)
    db.commit()

    # Viewer should get 404, not team info
    r = client.get(f"/api/posts/{tarea.id}/team-check", params={"u": "anyone"},
                   headers=_h(db, viewer))
    assert r.status_code == 404


def test_search_promotes_classmates_past_alphabetic_sort(client, db, klass):
    """Classmates must appear first even if their usernames sort after many
    non-classmates. Without SQL-level ordering (classmates first), a query
    with limit(50) could cut off classmates that sort alphabetically late."""
    me = _user(db, klass, "me")
    # Classmate with username that sorts late
    classmate = _user(db, klass, "bzz")
    # Create enough non-classmates with "b" prefix to potentially push classmate
    # past the 50-row limit if sorting is done after fetch.
    for i in range(60):
        _user(db, None, f"ba{i:02d}")
    # Search for "b" — should get classmate first, then non-classmates
    results = _search(client, db, me, "b")
    assert results[0] == "bzz", f"Classmate 'bzz' should be first, got: {results[:3]}"
    assert len(results) == 8  # limit
