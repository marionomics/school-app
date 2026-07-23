from decimal import Decimal

from app.models import Attachment, Like, Post, PointsLedger, User


def _user(db, n):
    u = User(google_id=f"g-fm{n}", email=f"fm{n}@example.com", name=f"FM {n}")
    db.add(u)
    db.commit()
    return u


def test_post_defaults(db):
    u = _user(db, 1)
    p = Post(author_id=u.id, content="hola")
    db.add(p)
    db.commit()
    db.refresh(p)
    assert p.type == "regular"
    assert p.status == "active"
    assert p.like_count == 0 and p.reply_count == 0
    assert p.taps is None and p.class_id is None and p.parent_id is None
    assert p.last_activity_at is not None


def test_reply_and_attachment(db):
    u = _user(db, 2)
    root = Post(author_id=u.id, content="root")
    db.add(root)
    db.commit()
    reply = Post(author_id=u.id, content="re", parent_id=root.id)
    att = Attachment(post_id=root.id, file_key="posts/x", file_name="x.pdf",
                     file_size=10, mime_type="application/pdf")
    db.add_all([reply, att])
    db.commit()
    db.refresh(root)
    assert reply.parent_id == root.id
    assert root.attachments[0].file_name == "x.pdf"


def test_ledger_decimal_points(db):
    u = _user(db, 3)
    row = PointsLedger(user_id=u.id, class_id=None, source_type="adjustment",
                       source_id=0, points=Decimal("1.5"))
    db.add(row)
    db.commit()
    db.refresh(row)
    assert row.points == Decimal("1.50")
    assert row.revoked_at is None


def test_like_unique(db):
    u = _user(db, 4)
    p = Post(author_id=u.id, content="p")
    db.add(p)
    db.commit()
    db.add(Like(user_id=u.id, post_id=p.id))
    db.commit()
    import pytest as _pytest
    from sqlalchemy.exc import IntegrityError
    db.add(Like(user_id=u.id, post_id=p.id))
    with _pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
