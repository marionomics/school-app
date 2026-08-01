"""The grade engine. Pure functions over the ledger and the post tree.

Grades are computed, never stored. All arithmetic is Decimal — no float
ever touches a grade.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import (AttendanceRecord, Class, ClassSession, PointsConfig,
                        PointsLedger, Post, Review)

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


def counting_review(db: Session, item_post_id: int, student_id: int,
                    entrega: Optional[Post]) -> Optional[Review]:
    """The review for this (item, student), unless it is stale.

    A review is stale when it was written against a submission the student has
    since replaced — grading someone early must not freeze their score against
    work that no longer exists. A paper examen has no entrega and never goes
    stale.
    """
    review = (
        db.query(Review)
        .filter(Review.item_post_id == item_post_id,
                Review.student_id == student_id)
        .first()
    )
    if review is None:
        return None
    if review.entrega_post_id is None:
        return review
    if entrega is None or review.entrega_post_id != entrega.id:
        return None
    return review


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
        review = counting_review(db, tarea.id, user_id, entrega)
        if review is not None and review.score is not None:
            total += Decimal(review.score)          # already 0–100 for a tarea
        else:
            total += lateness_score(entrega.created_at, tarea.due_date)

    points = (total / len(due_tareas) / Decimal("100")) * weight
    return Rubro(evaluated=True, points=points, weight=weight,
                 count_due=len(due_tareas), count_entregadas=entregadas)


FALTA_COST = Decimal("10")


def like_points(n: int, like_value: Decimal, exponent: Decimal) -> Decimal:
    """Concave by default: the nth like is worth sqrt(n) - sqrt(n-1), not 1.

    NEVER sum the points column of forum_like ledger rows — those rows are the
    event log. This function is the only source of like points.
    """
    if n <= 0:
        return Decimal("0")
    exponent = Decimal(exponent)
    if exponent == Decimal("1"):
        base = Decimal(n)
    elif exponent == Decimal("0.5"):
        base = Decimal(n).sqrt()
    else:
        base = (Decimal(n).ln() * exponent).exp()
    return Decimal(like_value) * base


def ledger_breakdown(db: Session, user_id: int, class_id: int) -> dict:
    rows = (
        db.query(PointsLedger)
        .filter(PointsLedger.user_id == user_id,
                PointsLedger.class_id == class_id,
                PointsLedger.revoked_at.is_(None))
        .all()
    )
    cfg = get_config(db, class_id)
    participaciones = sum((r.points for r in rows if r.source_type == "participacion"),
                          Decimal("0"))
    likes_count = sum(1 for r in rows if r.source_type == "forum_like")
    other = sum((r.points for r in rows
                 if r.source_type not in ("participacion", "forum_like")),
                Decimal("0"))
    return {
        "participaciones": participaciones,
        "likes": like_points(likes_count, cfg.like_value, cfg.like_exponent),
        "likes_count": likes_count,
        "other": other,
    }


def faltas_breakdown(db: Session, user_id: int, class_id: int) -> tuple[int, Decimal]:
    """Unjustified absences only.

    The NULL case is spelled out: `!= 'approved'` alone silently drops NULL
    rows in SQL, and justification_status is nullable.
    """
    count = (
        db.query(AttendanceRecord)
        .join(ClassSession, AttendanceRecord.session_id == ClassSession.id)
        .filter(ClassSession.class_id == class_id,
                AttendanceRecord.user_id == user_id,
                AttendanceRecord.status == "absent",
                or_(AttendanceRecord.justification_status.is_(None),
                    AttendanceRecord.justification_status != "approved"))
        .count()
    )
    return count, Decimal(count) * FALTA_COST


@dataclass
class GradeBreakdown:
    tareas: Rubro
    examenes: Rubro
    ledger: dict
    faltas_count: int
    faltas_points: Decimal
    total: Decimal


def examenes_rubro(db: Session, user_id: int, klass: Class, now: datetime) -> Rubro:
    """An examen counts only once the teacher marks it calificado.

    Unlike a tarea, an examen has no auto-score: until somebody types a number
    there is nothing to average, so an ungraded examen stays invisible instead
    of reading as a zero. Once graded, it counts for every active enrollment —
    a student with no review scored 0, which is the 'didn't take it' case.
    """
    graded = (
        db.query(Post)
        .filter(Post.class_id == klass.id,
                Post.type == "examen",
                Post.status == "active",
                Post.graded_at.isnot(None))
        .all()
    )
    weight = klass.examenes_weight
    if not graded:
        return Rubro(evaluated=False, points=Decimal("0"), weight=weight)

    total = Decimal("0")
    entregadas = 0
    for examen in graded:
        entrega = _counting_entrega(db, user_id, examen.id)
        if entrega is not None:
            entregadas += 1
        review = counting_review(db, examen.id, user_id, entrega)
        if review is not None and review.score is not None:
            total += Decimal(review.score) / Decimal("10")   # 1–10 scale
    points = (total / len(graded)) * weight
    return Rubro(evaluated=True, points=points, weight=weight,
                 count_due=len(graded), count_entregadas=entregadas)


def calculate_grade(db: Session, user_id: int, klass: Class,
                    now: datetime) -> GradeBreakdown:
    tareas = tareas_rubro(db, user_id, klass, now)
    examenes = examenes_rubro(db, user_id, klass, now)
    ledger = ledger_breakdown(db, user_id, klass.id)
    faltas_count, faltas_points = faltas_breakdown(db, user_id, klass.id)

    total = Decimal("0")
    if tareas.evaluated:
        total += tareas.points
    if examenes.evaluated:
        total += examenes.points
    total += ledger["participaciones"] + ledger["likes"] + ledger["other"]
    total -= faltas_points

    return GradeBreakdown(tareas=tareas, examenes=examenes, ledger=ledger,
                          faltas_count=faltas_count, faltas_points=faltas_points,
                          total=total)
