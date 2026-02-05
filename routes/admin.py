"""
Admin routes for teacher functionality.
"""
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from models.database import get_db
from models.models import Student, Attendance, Participation, Grade, Class, StudentClass
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
    class_id: Optional[int] = None,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """List students. If class_id provided, list only enrolled students."""
    if class_id:
        # Verify teacher owns this class
        class_ = db.query(Class).filter(
            Class.id == class_id,
            Class.teacher_id == teacher.id,
        ).first()
        if not class_:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clase no encontrada",
            )
        # Get students enrolled in this class
        enrollments = db.query(StudentClass).filter(
            StudentClass.class_id == class_id
        ).all()
        students = [e.student for e in enrollments]
    else:
        students = db.query(Student).filter(Student.role == "student").all()
    return students


@router.post("/attendance", response_model=list[AttendanceResponse])
async def record_attendance(
    data: BulkAttendanceCreate,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Record attendance for multiple students in a class."""
    # Verify teacher owns this class
    class_ = db.query(Class).filter(
        Class.id == data.class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clase no encontrada",
        )

    attendance_date = data.date or date.today()
    results = []

    for record in data.records:
        # Check if attendance already exists for this student, date, and class
        existing = db.query(Attendance).filter(
            Attendance.student_id == record.student_id,
            Attendance.class_id == data.class_id,
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
                class_id=data.class_id,
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
    class_id: int,
    date: Optional[str] = None,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Get attendance records for a specific class and optionally a date."""
    # Verify teacher owns this class
    class_ = db.query(Class).filter(
        Class.id == class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clase no encontrada",
        )

    query = db.query(Attendance).filter(Attendance.class_id == class_id)

    if date:
        from datetime import datetime
        try:
            attendance_date = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.filter(Attendance.date == attendance_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de fecha invalido. Usa YYYY-MM-DD.",
            )

    return query.order_by(Attendance.date.desc()).all()


@router.post("/grades", response_model=GradeResponse)
async def add_grade(
    data: GradeCreate,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Add a grade for a student in a class."""
    # Verify teacher owns this class
    class_ = db.query(Class).filter(
        Class.id == data.class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clase no encontrada",
        )

    # Verify student exists and is enrolled in the class
    enrollment = db.query(StudentClass).filter(
        StudentClass.student_id == data.student_id,
        StudentClass.class_id == data.class_id,
    ).first()
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estudiante no encontrado en esta clase",
        )

    grade = Grade(
        student_id=data.student_id,
        class_id=data.class_id,
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
    class_id: int,
    status_filter: Optional[str] = None,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Get participation submissions for a class with student info."""
    # Verify teacher owns this class
    class_ = db.query(Class).filter(
        Class.id == class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clase no encontrada",
        )

    query = db.query(Participation).join(Student).filter(
        Participation.class_id == class_id
    )

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
