"""Teacher surfaces agree with the engine on team submissions (spec §2–§3)."""
from datetime import datetime, timedelta, timezone

from datetime import date

from app.models import Enrollment, Post, PostMention, Review, User, utcnow
from app.services.feed_query import teacher_pending
from app.services.grades import _counting_entrega

# Fixed past dates for posts, real "now" for pending: reviews saved through the
# API get updated_at = utcnow(), and teacher_pending only counts what happened
# at or before as_of. The class is kept running so the test doesn't expire.
DUE = datetime(2026, 8, 9, 23, 59, tzinfo=timezone.utc)
NOW = utcnow() + timedelta(days=1)


def _running(db, klass):
    klass.end_date = date(2099, 1, 1)
    db.commit()


def _user(db, klass, handle, status="active"):
    u = User(google_id=f"g-{handle}", email=f"{handle}@example.com",
             name=handle.title(), username=handle)
    db.add(u)
    db.flush()
    db.add(Enrollment(user_id=u.id, class_id=klass.id, status=status))
    db.commit()
    return u


def _sub(db, author, item, team=(), is_entrega=True, at=DUE):
    p = Post(author_id=author.id, class_id=item.class_id, parent_id=item.id,
             content="x", is_entrega=is_entrega, created_at=at)
    db.add(p)
    db.flush()
    for u in team:
        db.add(PostMention(post_id=p.id, user_id=u.id, kind="team"))
    db.commit()
    return p


def _tarea(db, teacher, klass):
    t = Post(author_id=teacher.id, class_id=klass.id, type="tarea", content="T",
             due_date=DUE, created_at=DUE - timedelta(days=3))
    db.add(t)
    db.commit()
    return t


def test_entregas_queue_has_one_row_per_team(client, db, teacher, teacher_headers, klass):
    ana, pedro, luis, eva = (_user(db, klass, n) for n in ("ana", "pedro", "luis", "eva"))
    t = _tarea(db, teacher, klass)
    e = _sub(db, ana, t, team=[pedro, luis])
    _sub(db, eva, t)
    g = client.get(f"/api/review/entregas?class_id={klass.id}",
                   headers=teacher_headers).json()["groups"][0]
    assert g["pending"] == 2
    row = next(r for r in g["entregas"] if r["entrega_post_id"] == e.id)
    assert row["student"]["username"] == "ana"
    assert [(m["user"]["username"], m["removed"]) for m in row["team"]] == [
        ("pedro", False), ("luis", False)]


def test_grading_a_member_writes_the_authors_review(client, db, teacher, teacher_headers, klass):
    ana, pedro = _user(db, klass, "ana"), _user(db, klass, "pedro")
    t = _tarea(db, teacher, klass)
    e = _sub(db, ana, t, team=[pedro])
    r = client.put("/api/reviews", json={"item_post_id": t.id, "student_id": pedro.id,
                                         "entrega_post_id": e.id, "score": 85},
                   headers=teacher_headers)
    assert r.status_code == 200, r.text
    assert [rv.student_id for rv in db.query(Review).all()] == [ana.id]


def test_grading_someone_with_an_entrega_that_isnt_theirs_is_rejected(
        client, db, teacher, teacher_headers, klass):
    ana, eva = _user(db, klass, "ana"), _user(db, klass, "eva")
    t = _tarea(db, teacher, klass)
    e = _sub(db, ana, t)
    r = client.put("/api/reviews", json={"item_post_id": t.id, "student_id": eva.id,
                                         "entrega_post_id": e.id, "score": 85},
                   headers=teacher_headers)
    assert r.status_code == 422


def test_pending_counts_one_per_team_and_agrees_with_the_engine(db, teacher, klass):
    _running(db, klass)
    ana, pedro, luis, eva = (_user(db, klass, n) for n in ("ana", "pedro", "luis", "eva"))
    t = _tarea(db, teacher, klass)
    _sub(db, pedro, t, at=DUE - timedelta(hours=5))          # replaced by the team's
    e = _sub(db, ana, t, team=[pedro, luis])
    _sub(db, eva, t)
    assert teacher_pending(db, teacher.id, NOW)[t.id][1] == 2
    engine = {_counting_entrega(db, u.id, t.id).id for u in (ana, pedro, luis, eva)}
    assert len(engine) == 2 and e.id in engine
    db.add(Review(item_post_id=t.id, student_id=ana.id, entrega_post_id=e.id, score=80,
                  created_at=DUE, updated_at=DUE))
    db.commit()
    assert teacher_pending(db, teacher.id, NOW)[t.id][1] == 1


def test_a_ghost_author_still_counts_for_active_members(client, db, teacher, teacher_headers, klass):
    _running(db, klass)
    ana, pedro = _user(db, klass, "ana"), _user(db, klass, "pedro")
    t = _tarea(db, teacher, klass)
    e = _sub(db, ana, t, team=[pedro])
    db.query(Enrollment).filter(Enrollment.user_id == ana.id).update({"status": "ghost"})
    db.commit()
    assert teacher_pending(db, teacher.id, NOW)[t.id][1] == 1
    r = client.put("/api/reviews", json={"item_post_id": t.id, "student_id": pedro.id,
                                         "entrega_post_id": e.id, "score": 70},
                   headers=teacher_headers)
    assert r.status_code == 200, r.text
    assert t.id not in teacher_pending(db, teacher.id, NOW)


def test_examen_roster_shows_the_team_and_the_shared_score(client, db, teacher, teacher_headers, klass):
    ana, pedro = _user(db, klass, "ana"), _user(db, klass, "pedro")
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen", content="P",
             examen_mode="digital")
    db.add(x)
    db.commit()
    sub = _sub(db, ana, x, team=[pedro])           # marked entrega
    client.put("/api/reviews", json={"item_post_id": x.id, "student_id": pedro.id,
                                     "score": 9}, headers=teacher_headers)
    rows = {r["student"]["username"]: r for r in client.get(
        f"/api/review/examenes/{x.id}", headers=teacher_headers).json()["rows"]}
    assert rows["pedro"]["team_of"]["username"] == "ana"
    assert rows["ana"]["team_of"] is None
    assert rows["pedro"]["score"] == rows["ana"]["score"] == 9.0
    assert rows["pedro"]["submission"]["post_id"] == sub.id


def test_the_thread_marks_a_team_examen_submission_once(client, db, teacher, teacher_headers, klass):
    ana, pedro = _user(db, klass, "ana"), _user(db, klass, "pedro")
    x = Post(author_id=teacher.id, class_id=klass.id, type="examen", content="P",
             examen_mode="digital")
    db.add(x)
    db.commit()
    sub = _sub(db, ana, x, team=[pedro])
    client.put("/api/reviews", json={"item_post_id": x.id, "student_id": ana.id,
                                     "score": 8}, headers=teacher_headers)
    replies = {r["id"]: r for r in client.get(
        f"/api/posts/{x.id}", headers=teacher_headers).json()["replies"]}
    assert replies[sub.id]["is_submission"] is True
    assert float(replies[sub.id]["my_review"]["score"]) == 8.0


def test_accept_suggested_grades_a_team_entrega_once(client, db, teacher, teacher_headers, klass):
    ana, pedro = _user(db, klass, "ana"), _user(db, klass, "pedro")
    t = _tarea(db, teacher, klass)
    e = _sub(db, ana, t, team=[pedro])
    r = client.post("/api/reviews/accept-suggested",
                    json={"item_post_id": t.id, "entrega_post_ids": [e.id]},
                    headers=teacher_headers)
    assert r.json() == {"graded": 1}
    assert db.query(Review).count() == 1
