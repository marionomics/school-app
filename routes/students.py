from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional

from models.database import get_db
from models.models import Student, Attendance, Grade
from models.schemas import StudentResponse, AttendanceResponse, GradeResponse
from app.auth import get_current_student

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
