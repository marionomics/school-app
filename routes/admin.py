"""
Admin routes for teacher functionality.
"""
import logging
from datetime import date, datetime as dt
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)

from models.database import get_db
from models.models import (
    Student, Attendance, Participation, Grade, Class, StudentClass,
    GradeCategory, SpecialPoints, Assignment, Submission
)
from models.schemas import (
    StudentResponse,
    AttendanceResponse,
    GradeCreate,
    GradeResponse,
    BulkAttendanceCreate,
    ParticipationUpdate,
    BulkParticipationApprove,
    ParticipationWithStudent,
    GradeCategoryCreate,
    GradeCategoryResponse,
    GradeCategoryUpdate,
    SpecialPointsCreate,
    SpecialPointsResponse,
    SpecialPointsUpdate,
    CategoryGradeBreakdown,
    StudentRosterEntry,
    AssignmentCreate,
    AssignmentResponse,
    SubmissionResponse,
    SubmissionWithStudent,
    SubmissionGradeRequest,
    AssignmentSubmissionsResponse,
    AutoGradeResult,
    JustificationReviewRequest,
    AttendanceWithStudent,
    ClassSettingsUpdate,
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
    logger.info(f"Recording attendance: class_id={data.class_id}, date={data.date}, records={len(data.records)}")

    # Verify teacher owns this class
    class_ = db.query(Class).filter(
        Class.id == data.class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        logger.error(f"Class not found or not owned by teacher: class_id={data.class_id}, teacher_id={teacher.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clase no encontrada",
        )

    attendance_date = data.date or date.today()
    results = []

    try:
        for record in data.records:
            # Verify student is enrolled in this class
            enrollment = db.query(StudentClass).filter(
                StudentClass.student_id == record.student_id,
                StudentClass.class_id == data.class_id,
            ).first()
            if not enrollment:
                logger.warning(f"Student {record.student_id} not enrolled in class {data.class_id}")
                # Skip this student but continue with others
                continue

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
                results.append(attendance)

        # Commit all changes at once
        db.commit()
        for r in results:
            db.refresh(r)

        logger.info(f"Successfully saved {len(results)} attendance records")
        return results

    except Exception as e:
        db.rollback()
        logger.error(f"Database error saving attendance: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar asistencia: {str(e)}",
        )


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
        try:
            attendance_date = dt.strptime(date, "%Y-%m-%d").date()
            query = query.filter(Attendance.date == attendance_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de fecha invalido. Usa YYYY-MM-DD.",
            )

    records = query.order_by(Attendance.date.desc()).all()
    return [
        AttendanceResponse(
            id=att.id,
            student_id=att.student_id,
            date=att.date,
            status=att.status,
            notes=att.notes,
            justification_status=att.justification_status,
            justification_text=att.justification_text,
            justification_file_name=att.justification_file_name,
            justification_submitted_at=att.justification_submitted_at,
            has_justification_file=bool(att.justification_file_key),
        )
        for att in records
    ]


@router.get("/justifications", response_model=List[AttendanceWithStudent])
async def get_pending_justifications(
    class_id: int,
    status_filter: Optional[str] = None,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Get attendance records with pending (or filtered) justifications for a class."""
    class_ = db.query(Class).filter(
        Class.id == class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Clase no encontrada")

    query = db.query(Attendance).join(Student, Attendance.student_id == Student.id).filter(
        Attendance.class_id == class_id,
        Attendance.justification_status.isnot(None),
    )

    if status_filter:
        query = query.filter(Attendance.justification_status == status_filter)
    else:
        query = query.filter(Attendance.justification_status == "pending")

    records = query.order_by(Attendance.date.desc()).all()

    results = []
    for att in records:
        student = att.student
        results.append(AttendanceWithStudent(
            id=att.id,
            student_id=att.student_id,
            date=att.date,
            status=att.status,
            notes=att.notes,
            justification_status=att.justification_status,
            justification_text=att.justification_text,
            justification_file_name=att.justification_file_name,
            justification_submitted_at=att.justification_submitted_at,
            has_justification_file=bool(att.justification_file_key),
            student_name=student.name,
            student_email=student.email,
        ))

    return results


@router.patch("/justifications/{attendance_id}")
async def review_justification(
    attendance_id: int,
    data: JustificationReviewRequest,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Approve or reject a justification."""
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not attendance:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    # Verify teacher owns the class
    class_ = db.query(Class).filter(
        Class.id == attendance.class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    if attendance.justification_status is None:
        raise HTTPException(status_code=400, detail="No hay justificacion enviada")

    if data.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Estado debe ser 'approved' o 'rejected'")

    attendance.justification_status = data.status
    attendance.justification_reviewed_at = dt.utcnow()
    attendance.justification_reviewed_by = teacher.id

    # If approved, change attendance status to excused
    if data.status == "approved":
        attendance.status = "excused"

    db.commit()
    db.refresh(attendance)

    student = attendance.student
    return AttendanceWithStudent(
        id=attendance.id,
        student_id=attendance.student_id,
        date=attendance.date,
        status=attendance.status,
        notes=attendance.notes,
        justification_status=attendance.justification_status,
        justification_text=attendance.justification_text,
        justification_file_name=attendance.justification_file_name,
        justification_submitted_at=attendance.justification_submitted_at,
        has_justification_file=bool(attendance.justification_file_key),
        student_name=student.name,
        student_email=student.email,
    )


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

    # If category_id provided, verify it belongs to this class and resolve its name
    category_name = data.category  # may be None if not sent by frontend
    if data.category_id:
        cat = db.query(GradeCategory).filter(
            GradeCategory.id == data.category_id,
            GradeCategory.class_id == data.class_id,
        ).first()
        if not cat:
            raise HTTPException(status_code=404, detail="Categoría no encontrada en esta clase")
        category_name = cat.name  # always use the real name from DB

    grade = Grade(
        student_id=data.student_id,
        class_id=data.class_id,
        category_id=data.category_id,
        category=category_name,
        name=data.name,
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


@router.patch("/participation/bulk-approve")
async def bulk_approve_participation(
    data: BulkParticipationApprove,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Approve multiple participation submissions at once."""
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

    item_ids = [item.id for item in data.items]
    points_map = {item.id: item.points for item in data.items}

    participations = db.query(Participation).filter(
        Participation.id.in_(item_ids),
        Participation.class_id == data.class_id,
        Participation.approved == "pending",
    ).all()

    if not participations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontraron participaciones pendientes",
        )

    for p in participations:
        p.approved = "approved"
        if points_map.get(p.id) is not None:
            p.points = points_map[p.id]

    db.commit()

    return {"approved_count": len(participations)}


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


# ==================== Grade Categories ====================

@router.get("/categories/{class_id}", response_model=List[GradeCategoryResponse])
async def get_grade_categories(
    class_id: int,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Get all grade categories for a class."""
    class_ = db.query(Class).filter(
        Class.id == class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Clase no encontrada")

    return db.query(GradeCategory).filter(GradeCategory.class_id == class_id).all()


@router.post("/categories/{class_id}", response_model=GradeCategoryResponse)
async def create_grade_category(
    class_id: int,
    data: GradeCategoryCreate,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Create a grade category for a class."""
    class_ = db.query(Class).filter(
        Class.id == class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Clase no encontrada")

    # Check if category name already exists
    existing = db.query(GradeCategory).filter(
        GradeCategory.class_id == class_id,
        GradeCategory.name == data.name,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe una categoria con ese nombre")

    category = GradeCategory(
        class_id=class_id,
        name=data.name,
        weight=data.weight,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.put("/categories/{class_id}/{category_id}", response_model=GradeCategoryResponse)
async def update_grade_category(
    class_id: int,
    category_id: int,
    data: GradeCategoryUpdate,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Update a grade category."""
    # Verify teacher owns the class
    class_ = db.query(Class).filter(
        Class.id == class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=403, detail="No tienes permiso para editar esta categoria")

    category = db.query(GradeCategory).filter(
        GradeCategory.id == category_id,
        GradeCategory.class_id == class_id,
    ).first()
    if not category:
        raise HTTPException(status_code=404, detail="Categoria no encontrada")

    if data.name is not None:
        category.name = data.name
    if data.weight is not None:
        category.weight = data.weight

    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{class_id}/{category_id}")
async def delete_grade_category(
    class_id: int,
    category_id: int,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Delete a grade category."""
    class_ = db.query(Class).filter(
        Class.id == class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    category = db.query(GradeCategory).filter(
        GradeCategory.id == category_id,
        GradeCategory.class_id == class_id,
    ).first()
    if not category:
        raise HTTPException(status_code=404, detail="Categoria no encontrada")

    db.delete(category)
    db.commit()
    return {"message": "Categoria eliminada"}


# ==================== Special Points ====================

@router.get("/special-points", response_model=List[SpecialPointsResponse])
async def get_special_points(
    class_id: int,
    student_id: Optional[int] = None,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Get special points for a class, optionally filtered by student."""
    class_ = db.query(Class).filter(
        Class.id == class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Clase no encontrada")

    query = db.query(SpecialPoints).filter(SpecialPoints.class_id == class_id)
    if student_id:
        query = query.filter(SpecialPoints.student_id == student_id)

    return query.all()


class SpecialPointsCreateFull(SpecialPointsCreate):
    """Extended schema with student_id and class_id."""
    student_id: int
    class_id: int


@router.post("/special-points", response_model=SpecialPointsResponse)
async def create_special_points(
    data: SpecialPointsCreateFull,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Create special points entry for a student."""
    class_ = db.query(Class).filter(
        Class.id == data.class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Clase no encontrada")

    # Verify student is enrolled
    enrollment = db.query(StudentClass).filter(
        StudentClass.student_id == data.student_id,
        StudentClass.class_id == data.class_id,
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Estudiante no inscrito en esta clase")

    # Check if already exists
    existing = db.query(SpecialPoints).filter(
        SpecialPoints.student_id == data.student_id,
        SpecialPoints.class_id == data.class_id,
        SpecialPoints.category == data.category,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un registro de puntos especiales para esta categoria")

    special = SpecialPoints(
        student_id=data.student_id,
        class_id=data.class_id,
        category=data.category,
        opted_in=data.opted_in,
    )
    db.add(special)
    db.commit()
    db.refresh(special)
    return special


@router.patch("/special-points/{special_id}", response_model=SpecialPointsResponse)
async def update_special_points(
    special_id: int,
    data: SpecialPointsUpdate,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Update special points (opt-in status or award)."""
    special = db.query(SpecialPoints).filter(SpecialPoints.id == special_id).first()
    if not special:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    class_ = db.query(Class).filter(
        Class.id == special.class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    if data.opted_in is not None:
        special.opted_in = data.opted_in
    if data.awarded is not None:
        special.awarded = data.awarded

    db.commit()
    db.refresh(special)
    return special


# ==================== Grade Calculation ====================

def _calc_grade(student_id: int, class_id: int, db: Session) -> dict:
    """Calculate grade using category weights, participation, and special points.

    Formula: Σ(category_avg × weight) + (participation × 0.1) + special_points
    In 'percentage' mode, final grade is capped at 100.
    """
    # Get class for grading mode
    class_ = db.query(Class).filter(Class.id == class_id).first()
    grading_mode = (class_.grading_mode if class_ and class_.grading_mode else None) or 'points'

    # Get categories for this class
    categories = db.query(GradeCategory).filter(
        GradeCategory.class_id == class_id
    ).all()

    # Get all grades for this student/class
    all_grades = db.query(Grade).filter(
        Grade.student_id == student_id,
        Grade.class_id == class_id,
    ).all()

    category_breakdowns = []
    weighted_sum = 0.0

    for cat in categories:
        cat_grades = [g for g in all_grades if g.category_id == cat.id]
        valid = [g for g in cat_grades if g.max_score and g.max_score > 0]
        avg = (sum((g.score / g.max_score) * 100 for g in valid) / len(valid)) if valid else 0.0
        contribution = avg * cat.weight
        weighted_sum += contribution

        # Assignment counts for this category
        cat_assignments = db.query(Assignment).filter(
            Assignment.class_id == class_id,
            Assignment.category_id == cat.id,
            Assignment.published == True,
        ).all()
        total_assignments = len(cat_assignments)

        graded_count = 0
        pending_count = 0
        for a in cat_assignments:
            sub = db.query(Submission).filter(
                Submission.assignment_id == a.id,
                Submission.student_id == student_id,
                Submission.submitted_at.isnot(None),
            ).first()
            if sub and sub.grade is not None:
                graded_count += 1
            elif sub:
                pending_count += 1

        category_breakdowns.append(CategoryGradeBreakdown(
            category_id=cat.id,
            category_name=cat.name,
            weight=cat.weight,
            grades=[GradeResponse(
                id=g.id, student_id=g.student_id, category_id=g.category_id,
                category=g.category, name=g.name, score=g.score,
                max_score=g.max_score, date=g.date,
            ) for g in cat_grades],
            average=avg,
            weighted_contribution=contribution,
            graded_count=graded_count,
            pending_count=pending_count,
            total_assignments=total_assignments,
        ))

    # Collect uncategorized grades (category_id is None)
    uncategorized = [g for g in all_grades if g.category_id is None]
    if uncategorized:
        valid_uncat = [g for g in uncategorized if g.max_score and g.max_score > 0]
        uncat_avg = (sum((g.score / g.max_score) * 100 for g in valid_uncat) / len(valid_uncat)) if valid_uncat else 0.0
        remaining_weight = max(0, 1.0 - sum(c.weight for c in categories)) if categories else 1.0
        uncat_contribution = uncat_avg * remaining_weight if remaining_weight > 0 else 0.0
        weighted_sum += uncat_contribution

        category_breakdowns.append(CategoryGradeBreakdown(
            category_id=None,
            category_name="Sin categoría",
            weight=remaining_weight,
            grades=[GradeResponse(
                id=g.id, student_id=g.student_id, category_id=g.category_id,
                category=g.category, name=g.name, score=g.score,
                max_score=g.max_score, date=g.date,
            ) for g in uncategorized],
            average=uncat_avg,
            weighted_contribution=uncat_contribution,
            graded_count=len(valid_uncat),
            pending_count=0,
            total_assignments=0,
        ))

    # Fallback: if no categories and no uncategorized grades
    if not categories and not uncategorized:
        valid = [g for g in all_grades if g.max_score and g.max_score > 0]
        weighted_sum = (sum((g.score / g.max_score) * 100 for g in valid) / len(valid)) if valid else 0.0

    # Participation bonus (no cap)
    part_pts = db.query(func.sum(Participation.points)).filter(
        Participation.student_id == student_id,
        Participation.class_id == class_id,
        Participation.approved == "approved",
    ).scalar() or 0

    part_contribution = 0.1 * int(part_pts)

    # Special points
    sp_records = db.query(SpecialPoints).filter(
        SpecialPoints.student_id == student_id,
        SpecialPoints.class_id == class_id,
    ).all()
    sp_total = sum(sp.points_value for sp in sp_records if sp.opted_in and sp.awarded)

    # Absence penalty: -1 per unjustified absence
    unjustified_absences = db.query(func.count(Attendance.id)).filter(
        Attendance.student_id == student_id,
        Attendance.class_id == class_id,
        Attendance.status == "absent",
        # Exclude absences with approved justification (those get status=excused)
    ).scalar() or 0
    absence_penalty = float(unjustified_absences)

    max_base_grade = sum(c.weight for c in categories) * 100
    final = weighted_sum + part_contribution + sp_total - absence_penalty
    if grading_mode == 'percentage':
        final = min(100.0, final)

    # Simple average for display (without weights)
    valid_all = [g for g in all_grades if g.max_score and g.max_score > 0]
    avg_grade = (sum((g.score / g.max_score) * 100 for g in valid_all) / len(valid_all)) if valid_all else 0.0

    return {
        "average_grade": avg_grade,
        "participation_points": int(part_pts),
        "participation_contribution": part_contribution,
        "special_points": sp_records,
        "special_points_total": sp_total,
        "category_breakdowns": category_breakdowns,
        "absence_count": unjustified_absences,
        "absence_penalty": absence_penalty,
        "final_grade": final,
        "grading_mode": grading_mode,
        "max_base_grade": max_base_grade,
    }


# ==================== Student Roster ====================

@router.get("/roster/{class_id}", response_model=List[StudentRosterEntry])
async def get_student_roster(
    class_id: int,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Get student roster with grades and attendance."""
    class_ = db.query(Class).filter(
        Class.id == class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Clase no encontrada")

    enrollments = db.query(StudentClass).filter(StudentClass.class_id == class_id).all()

    roster = []
    for enrollment in enrollments:
        student = enrollment.student
        if not student:
            continue

        att = db.query(Attendance).filter(
            Attendance.student_id == student.id,
            Attendance.class_id == class_id,
        ).all()
        present = sum(1 for a in att if a.status in ("present", "late"))
        att_rate = (present / len(att) * 100) if att else 0.0

        gd = _calc_grade(student.id, class_id, db)

        sp_responses = [SpecialPointsResponse(
            id=sp.id, student_id=sp.student_id, class_id=sp.class_id,
            category=sp.category, opted_in=sp.opted_in, awarded=sp.awarded,
            points_value=sp.points_value, created_at=sp.created_at,
        ) for sp in gd["special_points"]]

        roster.append(StudentRosterEntry(
            student=StudentResponse(
                id=student.id,
                name=student.name,
                email=student.email,
                role=student.role,
                created_at=student.created_at,
            ),
            attendance_rate=att_rate,
            participation_points=gd["participation_points"],
            grade_breakdown=gd["category_breakdowns"],
            special_points=sp_responses,
            final_grade=gd["final_grade"],
        ))

    return roster


# ==================== Class Dashboard ====================

from models.schemas import ClassDashboardResponse, ClassDashboardStats, StudentDashboardEntry


@router.get("/classes/{class_id}/dashboard")
async def get_class_dashboard(
    class_id: int,
    sort_by: str = "name",
    sort_order: str = "asc",
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Class dashboard using only core tables. No grade_categories/special_points."""
    logger.info(f"Dashboard requested for class_id={class_id}")

    # 1. Class info
    class_ = db.query(Class).filter(
        Class.id == class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Clase no encontrada")

    try:
        # 2. Enrolled students
        enrollments = db.query(StudentClass).filter(
            StudentClass.class_id == class_id
        ).all()
        logger.info(f"Class {class_id}: {len(enrollments)} students")

        # 3. Pending participation
        pending_participation = db.query(func.count(Participation.id)).filter(
            Participation.class_id == class_id,
            Participation.approved == "pending",
        ).scalar() or 0

        # 3b. Pending justifications
        pending_justifications = db.query(func.count(Attendance.id)).filter(
            Attendance.class_id == class_id,
            Attendance.justification_status == "pending",
        ).scalar() or 0

        # 4. Build student rows — one at a time, simple queries
        students_data = []
        total_att = 0.0
        total_grade = 0.0

        for enrollment in enrollments:
            student = enrollment.student
            if not student:
                continue

            # Attendance
            att_records = db.query(Attendance).filter(
                Attendance.student_id == student.id,
                Attendance.class_id == class_id,
            ).all()
            att_total = len(att_records)
            att_present = sum(1 for a in att_records if a.status in ("present", "late"))
            att_rate = (att_present / att_total * 100) if att_total > 0 else 0.0

            # Participation
            part_approved = db.query(func.sum(Participation.points)).filter(
                Participation.student_id == student.id,
                Participation.class_id == class_id,
                Participation.approved == "approved",
            ).scalar() or 0

            part_pending = db.query(func.count(Participation.id)).filter(
                Participation.student_id == student.id,
                Participation.class_id == class_id,
                Participation.approved == "pending",
            ).scalar() or 0

            # Grades
            gd = _calc_grade(student.id, class_id, db)

            # Last activity date
            last_att = db.query(func.max(Attendance.date)).filter(
                Attendance.student_id == student.id,
                Attendance.class_id == class_id,
            ).scalar()
            last_part = db.query(func.max(Participation.date)).filter(
                Participation.student_id == student.id,
                Participation.class_id == class_id,
            ).scalar()
            last_grd = db.query(func.max(Grade.date)).filter(
                Grade.student_id == student.id,
                Grade.class_id == class_id,
            ).scalar()

            dates = [d for d in [last_att, last_part, last_grd] if d is not None]
            last_activity = dt.combine(max(dates), dt.min.time()) if dates else None

            # Status
            final = gd["final_grade"]
            if att_rate < 60 or final < 60:
                sstatus = "at_risk"
            elif att_rate < 80 or final < 70:
                sstatus = "warning"
            else:
                sstatus = "good"

            students_data.append({
                "id": student.id,
                "name": student.name,
                "email": student.email,
                "attendance_rate": att_rate,
                "attendance_present": att_present,
                "attendance_total": att_total,
                "participation_points": int(part_approved),
                "participation_pending": int(part_pending),
                "average_grade": gd["average_grade"],
                "final_grade": final,
                "last_activity": last_activity.isoformat() if last_activity else None,
                "status": sstatus,
            })

            total_att += att_rate
            total_grade += final

        # 5. Filter
        if search:
            sl = search.lower()
            students_data = [s for s in students_data if sl in s["name"].lower() or sl in s["email"].lower()]

        if status_filter and status_filter != "all":
            students_data = [s for s in students_data if s["status"] == status_filter]

        # 6. Sort
        reverse = sort_order == "desc"
        sort_keys = {
            "name": lambda s: s["name"].lower(),
            "attendance": lambda s: s["attendance_rate"],
            "grade": lambda s: s["final_grade"],
            "participation": lambda s: s["participation_points"],
        }
        students_data.sort(key=sort_keys.get(sort_by, sort_keys["name"]), reverse=reverse)

        # 7. Stats
        n = len(enrollments)
        overall_att = (total_att / n) if n > 0 else 0.0
        avg_grade = (total_grade / n) if n > 0 else 0.0
        at_risk = sum(1 for s in students_data if s["status"] == "at_risk")
        top = sum(1 for s in students_data if s["final_grade"] >= 90)

        # 8. Recent activity
        recent = []

        for a in db.query(Attendance).filter(
            Attendance.class_id == class_id
        ).order_by(Attendance.date.desc()).limit(5).all():
            st = db.query(Student).filter(Student.id == a.student_id).first()
            recent.append({
                "type": "attendance",
                "date": str(a.date),
                "student_name": st.name if st else "Desconocido",
                "detail": f"Asistencia: {a.status}",
            })

        for p in db.query(Participation).filter(
            Participation.class_id == class_id
        ).order_by(Participation.date.desc()).limit(5).all():
            st = db.query(Student).filter(Student.id == p.student_id).first()
            desc = p.description or ""
            recent.append({
                "type": "participation",
                "date": str(p.date),
                "student_name": st.name if st else "Desconocido",
                "detail": f"Participación: {desc[:50]}" if len(desc) > 50 else f"Participación: {desc}",
                "status": p.approved,
            })

        recent.sort(key=lambda x: x["date"], reverse=True)
        recent = recent[:10]

        # 9. Load categories for this class
        class_categories = db.query(GradeCategory).filter(
            GradeCategory.class_id == class_id
        ).all()

        cat_responses = [GradeCategoryResponse(
            id=c.id, class_id=c.class_id, name=c.name,
            weight=c.weight, created_at=c.created_at,
        ) for c in class_categories]

        # 10. Return
        logger.info(f"Dashboard OK: class {class_id}, {len(students_data)} students")

        return {
            "stats": {
                "class_id": class_id,
                "class_name": class_.name,
                "class_code": class_.code,
                "total_students": n,
                "overall_attendance_rate": overall_att,
                "average_grade": avg_grade,
                "pending_participation": pending_participation,
                "students_at_risk": at_risk,
                "top_performers": top,
                "pending_justifications": pending_justifications,
                "categories": cat_responses,
                "grading_mode": class_.grading_mode or 'points',
            },
            "students": students_data,
            "recent_activity": recent,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dashboard error class {class_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error al cargar dashboard: {type(e).__name__}: {str(e)}",
        )


# ==================== Class Settings ====================

@router.patch("/classes/{class_id}/settings")
async def update_class_settings(
    class_id: int,
    data: ClassSettingsUpdate,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Update class settings (e.g., grading_mode)."""
    class_ = db.query(Class).filter(
        Class.id == class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Clase no encontrada")

    if data.grading_mode not in ('points', 'percentage'):
        raise HTTPException(status_code=400, detail="Modo invalido. Use 'points' o 'percentage'")

    class_.grading_mode = data.grading_mode
    db.commit()
    db.refresh(class_)

    return {"grading_mode": class_.grading_mode}


# ==================== Assignments ====================

@router.post("/assignments", response_model=AssignmentResponse)
async def create_assignment(
    data: AssignmentCreate,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Create an assignment (reto) for a class."""
    class_ = db.query(Class).filter(
        Class.id == data.class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Clase no encontrada")

    # Use provided category_id, or auto-find first category for this class
    category_id = data.category_id
    if category_id:
        # Verify category belongs to this class
        cat = db.query(GradeCategory).filter(
            GradeCategory.id == category_id,
            GradeCategory.class_id == data.class_id,
        ).first()
        if not cat:
            raise HTTPException(status_code=404, detail="Categoría no encontrada en esta clase")
    else:
        # Auto-find: first category for this class (typically "Retos de la Semana")
        first_cat = db.query(GradeCategory).filter(
            GradeCategory.class_id == data.class_id,
        ).first()
        if first_cat:
            category_id = first_cat.id

    # Default due_date: next Sunday 23:59
    due_date = data.due_date
    if not due_date:
        from datetime import timedelta
        today = date.today()
        days_until_sunday = (6 - today.weekday()) % 7
        if days_until_sunday == 0:
            days_until_sunday = 7
        next_sunday = today + timedelta(days=days_until_sunday)
        due_date = dt.combine(next_sunday, dt.min.time()).replace(hour=23, minute=59)

    assignment = Assignment(
        class_id=data.class_id,
        category_id=category_id,
        title=data.title,
        description=data.description,
        due_date=due_date,
        max_points=data.max_points or 100,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return AssignmentResponse(
        id=assignment.id,
        class_id=assignment.class_id,
        category_id=assignment.category_id,
        title=assignment.title,
        description=assignment.description,
        due_date=assignment.due_date,
        max_points=assignment.max_points,
        allow_late=assignment.allow_late,
        published=assignment.published,
        created_at=assignment.created_at,
        submission_count=0,
        graded_count=0,
    )


@router.get("/assignments", response_model=List[AssignmentResponse])
async def list_assignments(
    class_id: int,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """List assignments for a class with submission counts."""
    class_ = db.query(Class).filter(
        Class.id == class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Clase no encontrada")

    assignments = db.query(Assignment).filter(
        Assignment.class_id == class_id,
    ).order_by(Assignment.due_date.desc()).all()

    results = []
    for a in assignments:
        sub_count = db.query(func.count(Submission.id)).filter(
            Submission.assignment_id == a.id,
            Submission.submitted_at.isnot(None),
        ).scalar() or 0
        graded_count = db.query(func.count(Submission.id)).filter(
            Submission.assignment_id == a.id,
            Submission.submitted_at.isnot(None),
            Submission.grade.isnot(None),
        ).scalar() or 0

        results.append(AssignmentResponse(
            id=a.id,
            class_id=a.class_id,
            category_id=a.category_id,
            title=a.title,
            description=a.description,
            due_date=a.due_date,
            max_points=a.max_points,
            allow_late=a.allow_late,
            published=a.published,
            created_at=a.created_at,
            submission_count=sub_count,
            graded_count=graded_count,
        ))

    return results


@router.delete("/assignments/{assignment_id}")
async def delete_assignment(
    assignment_id: int,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Delete an assignment."""
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Reto no encontrado")

    # Verify teacher owns the class
    class_ = db.query(Class).filter(
        Class.id == assignment.class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    db.delete(assignment)
    db.commit()
    return {"message": "Reto eliminado"}


@router.get("/assignments/{assignment_id}/submissions", response_model=AssignmentSubmissionsResponse)
async def get_assignment_submissions(
    assignment_id: int,
    filter: Optional[str] = None,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Get all submissions for an assignment with student info."""
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Reto no encontrado")

    # Verify teacher owns the class
    class_ = db.query(Class).filter(
        Class.id == assignment.class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    # Get all active submissions with student info (exclude cleared/deleted)
    submissions = db.query(Submission).filter(
        Submission.assignment_id == assignment_id,
        Submission.submitted_at.isnot(None),
    ).all()

    # Apply filter
    if filter == "graded":
        submissions = [s for s in submissions if s.grade is not None]
    elif filter == "ungraded":
        submissions = [s for s in submissions if s.grade is None]
    elif filter == "late":
        submissions = [s for s in submissions if s.is_late]

    # Build submission responses with student info
    submission_responses = []
    submitter_ids = set()
    for s in submissions:
        student = db.query(Student).filter(Student.id == s.student_id).first()
        if not student:
            continue
        submitter_ids.add(s.student_id)
        auto_grade = (s.penalty_pct / 100) * assignment.max_points
        submission_responses.append(SubmissionWithStudent(
            id=s.id,
            assignment_id=s.assignment_id,
            student_id=s.student_id,
            text_content=s.text_content,
            drive_url=s.drive_url,
            submitted_at=s.submitted_at,
            is_late=s.is_late,
            penalty_pct=s.penalty_pct,
            grade=s.grade,
            feedback=s.feedback,
            graded_at=s.graded_at,
            student_name=student.name,
            student_email=student.email,
            auto_grade=auto_grade,
            file_name=s.file_name,
            file_size=s.file_size,
            has_file=bool(s.file_key),
            resubmit_count=s.resubmit_count or 0,
        ))

    # Build not_submitted list
    enrolled = db.query(StudentClass).filter(
        StudentClass.class_id == assignment.class_id,
    ).all()
    total_enrolled = len(enrolled)

    not_submitted = []
    for e in enrolled:
        if e.student_id not in submitter_ids:
            student = e.student
            if student:
                not_submitted.append(StudentResponse(
                    id=student.id,
                    name=student.name,
                    email=student.email,
                    role=student.role,
                    created_at=student.created_at,
                ))

    return AssignmentSubmissionsResponse(
        assignment_id=assignment.id,
        assignment_title=assignment.title,
        max_points=assignment.max_points,
        category_id=assignment.category_id,
        due_date=assignment.due_date,
        total_enrolled=total_enrolled,
        submissions=submission_responses,
        not_submitted=not_submitted,
    )


@router.patch("/submissions/{submission_id}/grade", response_model=SubmissionWithStudent)
async def grade_submission(
    submission_id: int,
    data: SubmissionGradeRequest,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Grade a single submission and upsert the corresponding Grade record."""
    submission = db.query(Submission).filter(
        Submission.id == submission_id,
    ).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Entrega no encontrada")

    assignment = db.query(Assignment).filter(
        Assignment.id == submission.assignment_id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Reto no encontrado")

    # Verify teacher owns the class
    class_ = db.query(Class).filter(
        Class.id == assignment.class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    # Validate score
    if data.score < 0 or data.score > assignment.max_points:
        raise HTTPException(
            status_code=400,
            detail=f"La calificacion debe estar entre 0 y {assignment.max_points}",
        )

    # Update submission
    submission.grade = data.score
    submission.feedback = data.feedback
    submission.graded_at = dt.utcnow()
    submission.graded_by = teacher.id

    # Resolve category from assignment, falling back to first class category
    resolved_category_id = assignment.category_id
    category_name = None
    if resolved_category_id:
        cat = db.query(GradeCategory).filter(GradeCategory.id == resolved_category_id).first()
        if cat:
            category_name = cat.name
    if not resolved_category_id:
        first_cat = db.query(GradeCategory).filter(
            GradeCategory.class_id == assignment.class_id
        ).first()
        if first_cat:
            resolved_category_id = first_cat.id
            category_name = first_cat.name
    if not category_name:
        category_name = "Retos de la Semana"

    # Upsert Grade record (match by student + class + assignment title)
    existing_grade = db.query(Grade).filter(
        Grade.student_id == submission.student_id,
        Grade.class_id == assignment.class_id,
        Grade.name == assignment.title,
    ).first()

    if existing_grade:
        existing_grade.score = data.score
        existing_grade.max_score = assignment.max_points
        existing_grade.category_id = resolved_category_id
        existing_grade.category = category_name
    else:
        grade = Grade(
            student_id=submission.student_id,
            class_id=assignment.class_id,
            category_id=resolved_category_id,
            category=category_name,
            name=assignment.title,
            score=data.score,
            max_score=assignment.max_points,
            date=date.today(),
        )
        db.add(grade)

    db.commit()
    db.refresh(submission)

    student = db.query(Student).filter(Student.id == submission.student_id).first()
    auto_grade = (submission.penalty_pct / 100) * assignment.max_points

    return SubmissionWithStudent(
        id=submission.id,
        assignment_id=submission.assignment_id,
        student_id=submission.student_id,
        text_content=submission.text_content,
        drive_url=submission.drive_url,
        submitted_at=submission.submitted_at,
        is_late=submission.is_late,
        penalty_pct=submission.penalty_pct,
        grade=submission.grade,
        feedback=submission.feedback,
        graded_at=submission.graded_at,
        student_name=student.name,
        student_email=student.email,
        auto_grade=auto_grade,
        file_name=submission.file_name,
        file_size=submission.file_size,
        has_file=bool(submission.file_key),
        resubmit_count=submission.resubmit_count or 0,
    )


@router.post("/assignments/{assignment_id}/auto-grade", response_model=AutoGradeResult)
async def auto_grade_assignment(
    assignment_id: int,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Auto-grade all ungraded submissions using penalty_pct * max_points."""
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Reto no encontrado")

    # Verify teacher owns the class
    class_ = db.query(Class).filter(
        Class.id == assignment.class_id,
        Class.teacher_id == teacher.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    # Resolve category from assignment, falling back to first class category
    resolved_category_id = assignment.category_id
    category_name = None
    if resolved_category_id:
        cat = db.query(GradeCategory).filter(GradeCategory.id == resolved_category_id).first()
        if cat:
            category_name = cat.name
    if not resolved_category_id:
        first_cat = db.query(GradeCategory).filter(
            GradeCategory.class_id == assignment.class_id
        ).first()
        if first_cat:
            resolved_category_id = first_cat.id
            category_name = first_cat.name
    if not category_name:
        category_name = "Retos de la Semana"

    # Get ungraded submissions
    ungraded = db.query(Submission).filter(
        Submission.assignment_id == assignment_id,
        Submission.grade.is_(None),
    ).all()

    graded_count = 0
    skipped_count = 0

    for s in ungraded:
        score = (s.penalty_pct / 100) * assignment.max_points
        s.grade = score
        s.graded_at = dt.utcnow()
        s.graded_by = teacher.id

        # Upsert Grade record
        existing_grade = db.query(Grade).filter(
            Grade.student_id == s.student_id,
            Grade.class_id == assignment.class_id,
            Grade.name == assignment.title,
        ).first()

        if existing_grade:
            existing_grade.score = score
            existing_grade.max_score = assignment.max_points
            existing_grade.category_id = resolved_category_id
            existing_grade.category = category_name
        else:
            grade = Grade(
                student_id=s.student_id,
                class_id=assignment.class_id,
                category_id=resolved_category_id,
                category=category_name,
                name=assignment.title,
                score=score,
                max_score=assignment.max_points,
                date=date.today(),
            )
            db.add(grade)

        graded_count += 1

    db.commit()

    return AutoGradeResult(
        graded_count=graded_count,
        skipped_count=skipped_count,
    )
