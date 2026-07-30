from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Class, Enrollment, PointsLedger, User, utcnow
from app.services.grades import tareas_rubro

router = APIRouter(prefix="/api/students/me", tags=["grades"])

_CENTS = Decimal("0.01")


def round_grade(value: Decimal) -> Decimal:
    """The single API-boundary rounding point: 2 dp, half-up (not banker's)."""
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _summary(db: Session, user_id: int, klass: Class) -> dict:
    rows = (
        db.query(PointsLedger)
        .filter(PointsLedger.user_id == user_id,
                PointsLedger.class_id == klass.id,
                PointsLedger.revoked_at.is_(None))
        .order_by(PointsLedger.created_at.desc())
        .all()
    )
    ledger_total = sum((r.points for r in rows), Decimal("0"))
    tareas = tareas_rubro(db, user_id, klass, now=utcnow())
    total = ledger_total + tareas.points   # stays Decimal end to end

    summary = {
        "class_id": klass.id,
        "class_name": klass.name,
        "total": float(round_grade(total)),
        "counts": {
            "participaciones": sum(1 for r in rows if r.source_type == "participacion"),
            "likes_received": sum(1 for r in rows if r.source_type == "forum_like"),
        },
        "events": [
            {"source_type": r.source_type, "points": float(r.points),
             "note": r.note, "created_at": r.created_at}
            for r in rows[:50]
        ],
        "tareas": {
            "evaluated": tareas.evaluated,
            "points": float(round_grade(tareas.points)),
            "weight": tareas.weight,
            "count_due": tareas.count_due,
            "count_entregadas": tareas.count_entregadas,
        },
    }
    return summary


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
