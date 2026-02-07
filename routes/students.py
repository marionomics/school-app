from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import logging

from models.database import get_db
from models.models import Student, Attendance, Grade, Participation, StudentClass
from models.schemas import (
    StudentResponse, AttendanceResponse, GradeResponse, ParticipationResponse,
)
from app.auth import get_current_student

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/students", tags=["students"])


@router.get("/me", response_model=StudentResponse)
async def get_current_student_info(
    current_student: Student = Depends(get_current_student)
):
    """Get current authenticated student's information."""
    return current_student


@router.get("/me/grades", response_model=List[GradeResponse])
async def get_student_grades(
    class_id: Optional[int] = None,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Get current student's grades. Optionally filter by class."""
    query = db.query(Grade).filter(Grade.student_id == current_student.id)
    if class_id:
        query = query.filter(Grade.class_id == class_id)
    return query.all()


@router.get("/me/attendance", response_model=List[AttendanceResponse])
async def get_student_attendance(
    class_id: Optional[int] = None,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Get current student's attendance records. Optionally filter by class."""
    query = db.query(Attendance).filter(
        Attendance.student_id == current_student.id
    )
    if class_id:
        query = query.filter(Attendance.class_id == class_id)
    return query.all()


@router.get("/me/participation", response_model=List[ParticipationResponse])
async def get_student_participation(
    class_id: Optional[int] = None,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Get current student's participation records. Optionally filter by class."""
    query = db.query(Participation).filter(
        Participation.student_id == current_student.id
    )
    if class_id:
        query = query.filter(Participation.class_id == class_id)

    participations = query.all()
    logger.info(f"Student {current_student.id} participation for class {class_id}: {len(participations)} records")
    return participations


@router.get("/me/participation/points")
async def get_student_participation_points(
    class_id: Optional[int] = None,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Get total approved participation points for current student."""
    query = db.query(func.sum(Participation.points)).filter(
        Participation.student_id == current_student.id,
        Participation.approved == "approved"
    )
    if class_id:
        query = query.filter(Participation.class_id == class_id)

    total_points = query.scalar() or 0
    logger.info(f"Student {current_student.id} total approved points for class {class_id}: {total_points}")
    return {"total_points": total_points, "class_id": class_id}


@router.get("/me/grade-calculation/{class_id}")
async def get_student_grade_calculation(
    class_id: int,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Get grade calculation breakdown for a class (simple average)."""
    enrollment = db.query(StudentClass).filter(
        StudentClass.student_id == current_student.id,
        StudentClass.class_id == class_id,
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="No estas inscrito en esta clase")

    # All grades for this student/class
    grades = db.query(Grade).filter(
        Grade.student_id == current_student.id,
        Grade.class_id == class_id,
    ).all()

    valid = [g for g in grades if g.max_score and g.max_score > 0]
    avg = sum((g.score / g.max_score) * 100 for g in valid) / len(valid) if valid else 0.0

    # Participation
    part_pts = db.query(func.sum(Participation.points)).filter(
        Participation.student_id == current_student.id,
        Participation.class_id == class_id,
        Participation.approved == "approved",
    ).scalar() or 0

    part_contribution = 0.1 * part_pts
    final_grade = min(avg + part_contribution, 100)

    return {
        "student_id": current_student.id,
        "student_name": current_student.name,
        "student_email": current_student.email,
        "grades": [
            {
                "id": g.id,
                "name": g.name,
                "category": g.category,
                "score": g.score,
                "max_score": g.max_score,
                "percentage": (g.score / g.max_score * 100) if g.max_score > 0 else 0,
                "date": str(g.date),
            } for g in grades
        ],
        "average_grade": avg,
        "participation_points": int(part_pts),
        "participation_contribution": part_contribution,
        "final_grade": final_grade,
    }
