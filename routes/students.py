from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import logging

from models.database import get_db
from models.models import Student, Attendance, Grade, Participation, GradeCategory, SpecialPoints, StudentClass
from models.schemas import (
    StudentResponse, AttendanceResponse, GradeResponse, ParticipationResponse,
    StudentGradeCalculation, CategoryGradeBreakdown, SpecialPointsResponse
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


@router.get("/me/grade-calculation/{class_id}", response_model=StudentGradeCalculation)
async def get_student_grade_calculation(
    class_id: int,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Get full grade calculation breakdown for a class."""
    # Verify student is enrolled in this class
    enrollment = db.query(StudentClass).filter(
        StudentClass.student_id == current_student.id,
        StudentClass.class_id == class_id,
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="No estas inscrito en esta clase")

    # Get grade categories
    categories = db.query(GradeCategory).filter(GradeCategory.class_id == class_id).all()

    category_breakdowns = []
    total_weighted = 0.0

    for cat in categories:
        # Get grades for this category
        grades = db.query(Grade).filter(
            Grade.student_id == current_student.id,
            Grade.class_id == class_id,
            Grade.category_id == cat.id,
        ).all()

        if grades:
            total_pct = sum((g.score / g.max_score) * 100 for g in grades)
            average = total_pct / len(grades)
        else:
            average = 0.0

        weighted = cat.weight * average
        total_weighted += weighted

        category_breakdowns.append(CategoryGradeBreakdown(
            category_id=cat.id,
            category_name=cat.name,
            weight=cat.weight,
            grades=[GradeResponse(
                id=g.id,
                student_id=g.student_id,
                category_id=g.category_id,
                category=g.category,
                name=g.name,
                score=g.score,
                max_score=g.max_score,
                date=g.date,
            ) for g in grades],
            average=average,
            weighted_contribution=weighted,
        ))

    # Get participation points
    participation_points = db.query(func.sum(Participation.points)).filter(
        Participation.student_id == current_student.id,
        Participation.class_id == class_id,
        Participation.approved == "approved",
    ).scalar() or 0

    participation_contribution = 0.1 * participation_points

    # Get special points
    special_points = db.query(SpecialPoints).filter(
        SpecialPoints.student_id == current_student.id,
        SpecialPoints.class_id == class_id,
    ).all()

    special_total = sum(
        sp.points_value for sp in special_points
        if sp.opted_in and sp.awarded
    )

    # Final grade calculation
    final_grade = total_weighted + participation_contribution + special_total

    return StudentGradeCalculation(
        student_id=current_student.id,
        student_name=current_student.name,
        student_email=current_student.email,
        categories=category_breakdowns,
        participation_points=participation_points,
        participation_contribution=participation_contribution,
        special_points=[
            SpecialPointsResponse(
                id=sp.id,
                student_id=sp.student_id,
                class_id=sp.class_id,
                category=sp.category,
                opted_in=sp.opted_in,
                awarded=sp.awarded,
                points_value=sp.points_value,
                created_at=sp.created_at,
            ) for sp in special_points
        ],
        special_points_total=special_total,
        final_grade=min(final_grade, 100),
    )
