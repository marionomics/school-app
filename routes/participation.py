from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import date

from models.database import get_db
from models.models import Student, Participation, StudentClass
from models.schemas import ParticipationCreate, ParticipationResponse
from app.auth import get_current_student

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

    db_participation = Participation(
        student_id=current_student.id,
        class_id=participation.class_id,
        date=date.today(),
        description=participation.description,
        points=participation.points
    )
    db.add(db_participation)
    db.commit()
    db.refresh(db_participation)
    return db_participation
