from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Class, Enrollment, PointsLedger, User

router = APIRouter(prefix="/api/students/me", tags=["grades"])


def _summary(db: Session, user_id: int, klass: Class) -> dict:
    rows = (
        db.query(PointsLedger)
        .filter(PointsLedger.user_id == user_id,
                PointsLedger.class_id == klass.id,
                PointsLedger.revoked_at.is_(None))
        .order_by(PointsLedger.created_at.desc())
        .all()
    )
    total = sum((r.points for r in rows), Decimal("0"))
    return {
        "class_id": klass.id,
        "class_name": klass.name,
        "total": float(total),
        "counts": {
            "participaciones": sum(1 for r in rows if r.source_type == "participacion"),
            "likes_received": sum(1 for r in rows if r.source_type == "forum_like"),
        },
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
