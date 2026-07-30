"""The grade engine. Pure functions over the ledger and the post tree.

Grades are computed, never stored. All arithmetic is Decimal — no float
ever touches a grade.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Class, PointsConfig, Post, Review

ON_TIME = Decimal("100")
UNDER_24H = Decimal("90")
UNDER_WEEK = Decimal("50")
LATE = Decimal("20")


@dataclass
class Rubro:
    evaluated: bool
    points: Decimal
    weight: int
    count_due: int = 0
    count_entregadas: int = 0


def lateness_score(entrega_at: datetime, due_at: datetime) -> Decimal:
    """Tier boundaries are closed at the top: exactly 24h -> 50, exactly 7d -> 20."""
    delta = entrega_at - due_at
    if delta <= timedelta(0):
        return ON_TIME
    if delta < timedelta(hours=24):
        return UNDER_24H
    if delta < timedelta(days=7):
        return UNDER_WEEK
    return LATE


def get_config(db: Session, class_id: int) -> PointsConfig:
    """Never returns None. A missing row must not be able to zero a grade."""
    cfg = db.query(PointsConfig).filter(PointsConfig.class_id == class_id).first()
    if cfg is not None:
        return cfg
    return PointsConfig(
        class_id=class_id,
        tap_value=Decimal("1.0"),
        like_value=Decimal("1.0"),
        like_exponent=Decimal("0.5"),
        like_cap=None,
        daily_post_limit=5,
    )


def _counting_entrega(db: Session, user_id: int, tarea_id: int) -> Optional[Post]:
    """Latest active entrega by this student on this tarea."""
    return (
        db.query(Post)
        .filter(Post.author_id == user_id,
                Post.parent_id == tarea_id,
                Post.is_entrega.is_(True),
                Post.status == "active")
        .order_by(Post.created_at.desc())
        .first()
    )


def tareas_rubro(db: Session, user_id: int, klass: Class, now: datetime) -> Rubro:
    due_tareas = (
        db.query(Post)
        .filter(Post.class_id == klass.id,
                Post.type == "tarea",
                Post.status == "active",
                Post.due_date.isnot(None),
                Post.due_date <= now)
        .all()
    )
    weight = klass.tareas_weight
    if not due_tareas:
        return Rubro(evaluated=False, points=Decimal("0"), weight=weight)

    total = Decimal("0")
    entregadas = 0
    for tarea in due_tareas:
        entrega = _counting_entrega(db, user_id, tarea.id)
        if entrega is None:
            continue
        entregadas += 1
        review = (
            db.query(Review)
            .filter(Review.entrega_post_id == entrega.id)
            .first()
        )
        if review is not None and review.score is not None:
            total += Decimal(review.score)          # already 0–100 for a tarea
        else:
            total += lateness_score(entrega.created_at, tarea.due_date)

    points = (total / len(due_tareas) / Decimal("100")) * weight
    return Rubro(evaluated=True, points=points, weight=weight,
                 count_due=len(due_tareas), count_entregadas=entregadas)
