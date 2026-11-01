from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import DEFAULT_STREAK_LEVELS, PointsConfig, Post, PostRoll
from app.services.grades import get_config


def test_a_post_loads_its_roll(db, student):
    p = Post(author_id=student.id, content="una publicación suficientemente larga")
    db.add(p)
    db.flush()
    db.add(PostRoll(post_id=p.id, multiplier=3, streak_days=7,
                    x2=Decimal("0.2"), x3=Decimal("0.05")))
    db.commit()
    db.expire_all()
    assert db.get(Post, p.id).roll.multiplier == 3


def test_one_roll_per_post(db, student):
    p = Post(author_id=student.id, content="x" * 30)
    db.add(p)
    db.flush()
    db.add(PostRoll(post_id=p.id, multiplier=1, streak_days=0, x2=0, x3=0))
    db.add(PostRoll(post_id=p.id, multiplier=2, streak_days=0, x2=0, x3=0))
    with pytest.raises(IntegrityError):
        db.commit()


def test_new_and_missing_configs_have_the_default_levels(db, klass):
    cfg = PointsConfig(class_id=klass.id)
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    assert cfg.streak_levels == DEFAULT_STREAK_LEVELS
    db.delete(cfg)
    db.commit()
    assert get_config(db, klass.id).streak_levels == DEFAULT_STREAK_LEVELS
