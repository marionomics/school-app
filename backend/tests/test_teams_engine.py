"""Team submissions in the grade engine (spec 2026-10-28, §2)."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models import Attachment, Enrollment, Post, PostMention, Review, User, utcnow
from app.services.grades import (_counting_entrega, counting_review, examen_submission,
                                 tareas_rubro)
from app.services.submissions import live_team_member_ids, team_of

DUE = datetime(2026, 8, 9, 23, 59, tzinfo=timezone.utc)
AFTER = datetime(2026, 8, 20, tzinfo=timezone.utc)


def _user(db, klass, handle, status="active"):
    u = User(google_id=f"g-{handle}", email=f"{handle}@example.com",
             name=handle.title(), username=handle)
    db.add(u)
    db.flush()
    db.add(Enrollment(user_id=u.id, class_id=klass.id, status=status))
    db.commit()
    return u


def _item(db, teacher, klass, type="tarea"):
    p = Post(author_id=teacher.id, class_id=klass.id, type=type, content="P",
             due_date=DUE if type == "tarea" else None,
             examen_mode="digital" if type == "examen" else None)
    db.add(p)
    db.commit()
    return p


def _sub(db, author, item, at, team=(), is_entrega=True, files=(), status="active"):
    p = Post(author_id=author.id, class_id=item.class_id, parent_id=item.id,
             content="x", is_entrega=is_entrega, created_at=at, status=status)
    db.add(p)
    db.flush()
    for u in team:
        db.add(PostMention(post_id=p.id, user_id=u.id, kind="team"))
    for name in files:
        db.add(Attachment(post_id=p.id, file_key=f"k/{name}", file_name=name,
                          file_size=10, mime_type="application/pdf"))
    db.commit()
    return p


def _team(db, klass):
    return _user(db, klass, "ana"), _user(db, klass, "pedro"), _user(db, klass, "luis")


def test_a_team_entrega_counts_for_every_member(db, teacher, klass):
    ana, pedro, luis = _team(db, klass)
    t = _item(db, teacher, klass)
    e = _sub(db, ana, t, DUE, team=[pedro, luis])
    for u in (ana, pedro, luis):
        assert _counting_entrega(db, u.id, t.id).id == e.id


def test_newer_wins_between_own_and_team(db, teacher, klass):
    ana, pedro, _ = _team(db, klass)
    t = _item(db, teacher, klass)
    draft = _sub(db, pedro, t, DUE - timedelta(hours=3))
    final = _sub(db, ana, t, DUE - timedelta(hours=2), team=[pedro])
    assert _counting_entrega(db, pedro.id, t.id).id == final.id
    mine_again = _sub(db, pedro, t, DUE - timedelta(hours=1))
    assert _counting_entrega(db, pedro.id, t.id).id == mine_again.id
    assert draft.id != mine_again.id


def test_author_replacing_without_tags_drops_the_team(db, teacher, klass):
    ana, pedro, _ = _team(db, klass)
    t = _item(db, teacher, klass)
    own = _sub(db, pedro, t, DUE - timedelta(hours=5))
    _sub(db, ana, t, DUE - timedelta(hours=2), team=[pedro])
    _sub(db, ana, t, DUE - timedelta(hours=1))          # Ana alone now
    assert _counting_entrega(db, pedro.id, t.id).id == own.id


def test_author_replacing_with_tags_carries_the_team(db, teacher, klass):
    ana, pedro, _ = _team(db, klass)
    t = _item(db, teacher, klass)
    _sub(db, ana, t, DUE - timedelta(hours=2), team=[pedro])
    v2 = _sub(db, ana, t, DUE - timedelta(hours=1), team=[pedro])
    assert _counting_entrega(db, pedro.id, t.id).id == v2.id


def test_a_removed_member_falls_back_to_nothing_or_their_own(db, teacher, klass):
    ana, pedro, luis = _team(db, klass)
    t = _item(db, teacher, klass)
    own = _sub(db, luis, t, DUE - timedelta(hours=5))
    e = _sub(db, ana, t, DUE - timedelta(hours=2), team=[pedro, luis])
    for m in e.mentions:
        m.removed_at = utcnow()
    db.commit()
    assert _counting_entrega(db, pedro.id, t.id) is None
    assert _counting_entrega(db, luis.id, t.id).id == own.id
    assert live_team_member_ids(db, e) == []


def test_deleted_or_vetoed_team_entrega_counts_for_nobody(db, teacher, klass):
    for status in ("deleted", "vetoed"):
        t = _item(db, teacher, klass)
        ana = _user(db, klass, f"ana_{status}")
        pedro = _user(db, klass, f"pedro_{status}")
        _sub(db, ana, t, DUE, team=[pedro], status=status)
        assert _counting_entrega(db, pedro.id, t.id) is None
        assert _counting_entrega(db, ana.id, t.id) is None


def test_a_member_reads_the_authors_review(db, teacher, klass):
    ana, pedro, _ = _team(db, klass)
    t = _item(db, teacher, klass)
    e = _sub(db, ana, t, DUE, team=[pedro])
    db.add(Review(item_post_id=t.id, student_id=ana.id, entrega_post_id=e.id,
                  score=Decimal("80")))
    db.commit()
    review = counting_review(db, t.id, pedro.id, e)
    assert review is not None and review.student_id == ana.id
    assert db.query(Review).filter(Review.student_id == pedro.id).count() == 0


def test_lateness_is_shared(db, teacher, klass):
    ana, pedro, _ = _team(db, klass)
    t = _item(db, teacher, klass)
    _sub(db, ana, t, DUE + timedelta(hours=3), team=[pedro])   # < 24 h late → 90
    a = tareas_rubro(db, ana.id, klass, AFTER)
    p = tareas_rubro(db, pedro.id, klass, AFTER)
    assert a.points == p.points == Decimal("0.9") * klass.tareas_weight


def test_examen_team_by_reply_with_files(db, teacher, klass):
    ana, pedro, _ = _team(db, klass)
    x = _item(db, teacher, klass, "examen")
    sub = _sub(db, ana, x, DUE, team=[pedro], is_entrega=False, files=["r.pdf"])
    assert examen_submission(db, pedro.id, x).id == sub.id
    assert _counting_entrega(db, pedro.id, x.id) is None   # not an entrega


def test_paper_examen_is_individual(db, teacher, klass):
    ana, _, _ = _team(db, klass)
    x = _item(db, teacher, klass, "examen")
    assert examen_submission(db, ana.id, x) is None
    db.add(Review(item_post_id=x.id, student_id=ana.id, score=Decimal("9")))
    db.commit()
    assert counting_review(db, x.id, ana.id, None).score == Decimal("9")


def test_team_of_sees_members_and_authors(db, teacher, klass):
    ana, pedro, luis = _team(db, klass)
    t = _item(db, teacher, klass)
    e = _sub(db, ana, t, DUE, team=[pedro])
    assert team_of(db, pedro.id, t).id == e.id      # as member
    assert team_of(db, ana.id, t).id == e.id        # as author of a team
    assert team_of(db, luis.id, t) is None
    assert team_of(db, pedro.id, t, ignore_author=ana.id) is None   # Ana re-tagging


def test_a_solo_author_is_not_on_a_team(db, teacher, klass):
    ana, _, _ = _team(db, klass)
    t = _item(db, teacher, klass)
    _sub(db, ana, t, DUE)
    assert team_of(db, ana.id, t) is None
