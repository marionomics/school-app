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
    GradeCategory, SpecialPoints
)
from models.schemas import (
    StudentResponse,
    AttendanceResponse,
    GradeCreate,
    GradeResponse,
    BulkAttendanceCreate,
    ParticipationUpdate,
    ParticipationWithStudent,
    GradeCategoryCreate,
    GradeCategoryResponse,
    GradeCategoryUpdate,
    SpecialPointsCreate,
    SpecialPointsResponse,
    SpecialPointsUpdate,
    CategoryGradeBreakdown,
    StudentRosterEntry,
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


# ==================== Grade Calculation (core tables only) ====================

def _calc_simple_grade(student_id: int, class_id: int, db: Session) -> dict:
    """Calculate grade using only core tables: grades + participations.
    No grade_categories or special_points queries."""

    # Simple average of all grades for this student/class
    grades = db.query(Grade).filter(
        Grade.student_id == student_id,
        Grade.class_id == class_id,
    ).all()

    valid = [g for g in grades if g.max_score and g.max_score > 0]
    if valid:
        avg = sum((g.score / g.max_score) * 100 for g in valid) / len(valid)
    else:
        avg = 0.0

    # Participation bonus
    part_pts = db.query(func.sum(Participation.points)).filter(
        Participation.student_id == student_id,
        Participation.class_id == class_id,
        Participation.approved == "approved",
    ).scalar() or 0

    final = min(avg + (0.1 * part_pts), 100)

    return {
        "average_grade": avg,
        "participation_points": int(part_pts),
        "final_grade": final,
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

        gd = _calc_simple_grade(student.id, class_id, db)

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
            grade_breakdown=[],
            special_points=[],
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
            gd = _calc_simple_grade(student.id, class_id, db)

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

        # 9. Return
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
                "categories": [],
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
