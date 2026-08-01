from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_teacher, get_current_user
from app.database import get_db
from app.models import Class, Enrollment, PointsLedger, User, utcnow
from app.schemas import RosterStudent
from app.services.grades import calculate_grade, faltas_breakdown

router = APIRouter(prefix="/api/students/me", tags=["grades"])

_CENTS = Decimal("0.01")


def round_grade(value: Decimal) -> Decimal:
    """The single API-boundary rounding point: 2 dp, half-up (not banker's)."""
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _rubro_json(r) -> dict:
    return {"evaluated": r.evaluated, "points": float(round_grade(r.points)),
            "weight": r.weight, "count_due": r.count_due,
            "count_entregadas": r.count_entregadas}


def _summary(db: Session, user_id: int, klass: Class) -> dict:
    g = calculate_grade(db, user_id, klass, now=utcnow())
    rows = (
        db.query(PointsLedger)
        .filter(PointsLedger.user_id == user_id,
                PointsLedger.class_id == klass.id,
                PointsLedger.revoked_at.is_(None))
        .order_by(PointsLedger.created_at.desc())
        .all()
    )
    return {
        "class_id": klass.id,
        "class_name": klass.name,
        "total": float(round_grade(g.total)),
        "tareas": _rubro_json(g.tareas),
        "examenes": _rubro_json(g.examenes),
        "ledger": {
            "participaciones": float(round_grade(g.ledger["participaciones"])),
            "likes": float(round_grade(g.ledger["likes"])),
            "likes_count": g.ledger["likes_count"],
            "other": float(round_grade(g.ledger["other"])),
        },
        "faltas": {"count": g.faltas_count, "points": float(round_grade(g.faltas_points))},
        "events": [
            {"source_type": r.source_type, "points": float(r.points),
             "note": r.note, "created_at": r.created_at}
            for r in rows[:50]
        ],
    }


@router.get("/grade")
def my_grade(class_id: Optional[int] = None, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    enrollments = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == user.id, Enrollment.status == "active")
        .all()
    )
    by_class = {e.class_id: e for e in enrollments}
    if class_id is not None:
        if class_id not in by_class:
            raise HTTPException(status_code=404, detail="No estás inscrito en esa clase")
        return _summary(db, user.id, db.get(Class, class_id))
    return [_summary(db, user.id, db.get(Class, cid)) for cid in by_class]


class_grades_router = APIRouter(tags=["grades"])


def _teacher_class(db: Session, class_id: int, teacher: User) -> Class:
    klass = db.get(Class, class_id)
    if klass is None:
        raise HTTPException(status_code=404, detail="Clase no encontrada")
    if klass.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="No eres profesor de esa clase")
    return klass


@class_grades_router.get("/api/classes/{class_id}/roster")
def class_roster(
    class_id: int,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    klass = _teacher_class(db, class_id, teacher)
    enrollments = (
        db.query(Enrollment)
        .filter(Enrollment.class_id == class_id)
        .all()
    )
    now = utcnow()
    students = []
    for e in enrollments:
        g = calculate_grade(db, e.user_id, klass, now=now)
        faltas_count, _ = faltas_breakdown(db, e.user_id, class_id)
        students.append(RosterStudent(
            id=e.user.id,
            name=e.user.name,
            username=e.user.username,
            avatar_url=e.user.avatar_url,
            status=e.status,
            grade=float(round_grade(g.total)),
            faltas=faltas_count,
        ))
    return {"students": students}


@class_grades_router.get("/api/classes/{class_id}/students/{student_id}/grade")
def student_grade_for_teacher(
    class_id: int,
    student_id: int,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    klass = _teacher_class(db, class_id, teacher)
    enrollment = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == student_id,
                Enrollment.class_id == class_id)
        .first()
    )
    if enrollment is None:
        raise HTTPException(status_code=404,
                            detail="Ese alumno no está en esta clase")
    return _summary(db, student_id, klass)
