import random

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import date

from models.database import get_db
from models.models import Student, Participation, StudentClass, Class
from models.schemas import ParticipationCreate, ParticipationResponse
from app.auth import get_current_student


def _roll_salvando_bonus(base: int) -> tuple:
    r = random.random()
    if r < 0.01:
        return 10, 'jackpot'
    if r < 0.11:
        return base * 3, 'triple'
    if r < 0.91:
        return base * 2, 'double'
    return base, 'normal'

router = APIRouter(prefix="/api", tags=["participation"])


@router.post("/participation", response_model=ParticipationResponse)
async def submit_participation(
    participation: ParticipationCreate,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Submit a participation entry for the current student in a class."""
    # Verify student is enrolled in the class
    enrollment = db.query(StudentClass).filter(
        StudentClass.student_id == current_student.id,
        StudentClass.class_id == participation.class_id,
    ).first()

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No estas inscrito en esta clase",
        )

    if len(participation.description.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La descripción debe tener al menos 5 caracteres",
        )

    points = participation.points or 1
    if points not in [1, 2, 3]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Los puntos deben ser 1, 2 o 3",
        )

    # Roll casino bonus immediately if Salvando el Semestre is active
    bonus_type = None
    class_ = db.query(Class).filter(Class.id == participation.class_id).first()
    if class_ and class_.salvando_semestre:
        points, bonus_type = _roll_salvando_bonus(points)

    db_participation = Participation(
        student_id=current_student.id,
        class_id=participation.class_id,
        date=date.today(),
        description=participation.description,
        points=points,
        bonus_type=bonus_type,
        source='class',
    )
    db.add(db_participation)
    db.commit()
    db.refresh(db_participation)
    return db_participation
