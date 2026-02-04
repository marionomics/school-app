from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date

from models.database import get_db
from models.models import Student, Participation
from models.schemas import ParticipationCreate, ParticipationResponse
from app.auth import get_current_student

router = APIRouter(prefix="/api", tags=["participation"])


@router.post("/participation", response_model=ParticipationResponse)
async def submit_participation(
    participation: ParticipationCreate,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Submit a participation entry for the current student."""
    db_participation = Participation(
        student_id=current_student.id,
        date=date.today(),
        description=participation.description,
        points=participation.points
    )
    db.add(db_participation)
    db.commit()
    db.refresh(db_participation)
    return db_participation
