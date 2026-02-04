"""
Admin routes for teacher functionality.
"""
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from models.database import get_db
from models.models import Student, Attendance, Participation, Grade
from models.schemas import (
    StudentResponse,
    AttendanceResponse,
    GradeCreate,
    GradeResponse,
    BulkAttendanceCreate,
    ParticipationUpdate,
    ParticipationWithStudent,
)
from app.auth import get_current_teacher

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/students", response_model=list[StudentResponse])
async def list_students(
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """List all students (excluding teachers)."""
    students = db.query(Student).filter(Student.role == "student").all()
    return students


@router.post("/attendance", response_model=list[AttendanceResponse])
async def record_attendance(
    data: BulkAttendanceCreate,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Record attendance for multiple students."""
    attendance_date = data.date or date.today()
    results = []

    for record in data.records:
        # Check if attendance already exists for this student and date
        existing = db.query(Attendance).filter(
            Attendance.student_id == record.student_id,
            Attendance.date == attendance_date,
        ).first()

        if existing:
            # Update existing record
            existing.status = record.status
            existing.notes = record.notes
            db.commit()
            db.refresh(existing)
            results.append(existing)
        else:
            # Create new record
            attendance = Attendance(
                student_id=record.student_id,
                date=attendance_date,
                status=record.status,
                notes=record.notes,
            )
            db.add(attendance)
            db.commit()
            db.refresh(attendance)
            results.append(attendance)

    return results


@router.get("/attendance", response_model=list[AttendanceResponse])
async def get_attendance(
    date: Optional[str] = None,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Get attendance records for a specific date."""
    query = db.query(Attendance)

    if date:
        from datetime import datetime
        try:
            attendance_date = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.filter(Attendance.date == attendance_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD.",
            )

    return query.order_by(Attendance.date.desc()).all()


@router.post("/grades", response_model=GradeResponse)
async def add_grade(
    data: GradeCreate,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Add a grade for a student."""
    # Verify student exists
    student = db.query(Student).filter(Student.id == data.student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    grade = Grade(
        student_id=data.student_id,
        category=data.category,
        score=data.score,
        max_score=data.max_score,
        date=data.date or date.today(),
    )
    db.add(grade)
    db.commit()
    db.refresh(grade)
    return grade


@router.get("/participation", response_model=list[ParticipationWithStudent])
async def get_participation(
    status_filter: Optional[str] = None,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Get all participation submissions with student info."""
    query = db.query(Participation).join(Student)

    if status_filter:
        query = query.filter(Participation.approved == status_filter)

    participations = query.order_by(Participation.date.desc()).all()

    # Build response with student info
    results = []
    for p in participations:
        results.append(ParticipationWithStudent(
            id=p.id,
            student_id=p.student_id,
            date=p.date,
            description=p.description,
            points=p.points,
            approved=p.approved,
            student_name=p.student.name,
            student_email=p.student.email,
        ))

    return results


@router.patch("/participation/{participation_id}", response_model=ParticipationWithStudent)
async def update_participation(
    participation_id: int,
    data: ParticipationUpdate,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Approve or reject a participation submission."""
    participation = db.query(Participation).filter(
        Participation.id == participation_id
    ).first()

    if not participation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participation not found",
        )

    participation.approved = data.approved
    if data.points is not None:
        participation.points = data.points

    db.commit()
    db.refresh(participation)

    return ParticipationWithStudent(
        id=participation.id,
        student_id=participation.student_id,
        date=participation.date,
        description=participation.description,
        points=participation.points,
        approved=participation.approved,
        student_name=participation.student.name,
        student_email=participation.student.email,
    )
