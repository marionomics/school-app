import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Post, PostMention


def test_post_loads_its_mentions_in_order(db, student, teacher):
    p = Post(author_id=student.id, content="hola @profe")
    db.add(p)
    db.flush()
    db.add(PostMention(post_id=p.id, user_id=teacher.id, kind="social"))
    db.commit()
    db.expire_all()
    p = db.get(Post, p.id)
    assert [(m.user.id, m.kind, m.removed_at) for m in p.mentions] == [
        (teacher.id, "social", None)]


def test_one_row_per_post_and_user(db, student, teacher):
    p = Post(author_id=student.id, content="x")
    db.add(p)
    db.flush()
    db.add(PostMention(post_id=p.id, user_id=teacher.id, kind="social"))
    db.add(PostMention(post_id=p.id, user_id=teacher.id, kind="team"))
    with pytest.raises(IntegrityError):
        db.commit()
