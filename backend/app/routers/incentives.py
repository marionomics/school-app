from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_teacher
from app.database import get_db
from app.models import Class, Enrollment, Incentive, PointsLedger, User, utcnow
from app.schemas import AwardBody, IncentiveCreate, IncentiveOut, LedgerRowOut

router = APIRouter(tags=["incentives"])


def _owned_class(db: Session, class_id: int, teacher: User) -> Class:
    klass = db.get(Class, class_id)
    if klass is None:
        raise HTTPException(status_code=404, detail="Clase no encontrada")
    if klass.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="No eres profesor de esa clase")
    return klass


def _owned_incentive(db: Session, incentive_id: int, teacher: User) -> Incentive:
    inc = db.get(Incentive, incentive_id)
    if inc is None or inc.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Incentivo no encontrado")
    _owned_class(db, inc.class_id, teacher)
    return inc


@router.get("/api/classes/{class_id}/incentives")
def list_incentives(
    class_id: int,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    _owned_class(db, class_id, teacher)
    rows = (
        db.query(Incentive)
        .filter(Incentive.class_id == class_id, Incentive.deleted_at.is_(None))
        .order_by(Incentive.created_at)
        .all()
    )
    return {"incentives": [IncentiveOut.model_validate(r) for r in rows]}


@router.post(
    "/api/classes/{class_id}/incentives",
    response_model=IncentiveOut,
    status_code=201,
)
def create_incentive(
    class_id: int,
    body: IncentiveCreate,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    _owned_class(db, class_id, teacher)
    inc = Incentive(
        class_id=class_id,
        name=body.name,
        points=body.points,
        description=body.description,
    )
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc


@router.delete("/api/incentives/{incentive_id}", status_code=204)
def delete_incentive(
    incentive_id: int,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    inc = _owned_incentive(db, incentive_id, teacher)
    was_awarded = (
        db.query(PointsLedger)
        .filter(
            PointsLedger.source_type == "incentive",
            PointsLedger.source_id == incentive_id,
        )
        .first()
    )
    if was_awarded:
        inc.deleted_at = utcnow()
    else:
        db.delete(inc)
    db.commit()


@router.post("/api/incentives/{incentive_id}/award", response_model=LedgerRowOut)
def award_incentive(
    incentive_id: int,
    body: AwardBody,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    inc = _owned_incentive(db, incentive_id, teacher)
    enrolled = (
        db.query(Enrollment)
        .filter(
            Enrollment.user_id == body.student_id,
            Enrollment.class_id == inc.class_id,
            Enrollment.status == "active",
        )
        .first()
    )
    if enrolled is None:
        raise HTTPException(
            status_code=422, detail="Ese alumno no está inscrito en la clase"
        )
    row = PointsLedger(
        user_id=body.student_id,
        class_id=inc.class_id,
        source_type="incentive",
        source_id=incentive_id,
        points=inc.points,
        note=inc.name,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
