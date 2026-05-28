from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional
from datetime import datetime as _dt, timedelta
import logging

from models.database import get_db
from models.models import Student, Attendance, Grade, Participation, StudentClass, GradeCategory, SpecialPoints, Assignment, Submission, Class, ForumPoints, ForumPost, OnlineExamDraft
from models.schemas import (
    StudentResponse, AttendanceResponse, GradeResponse, ParticipationResponse,
    CategoryGradeBreakdown, SpecialPointsResponse,
    AssignmentStudentView, SubmissionCreate, SubmissionResponse,
    AttendanceWithStudent,
    ExamStatusResponse, ExamDraftRequest, OnlineExamSubmitRequest, OnlineExamSubmitResponse,
)
from app.auth import get_current_student, get_student_or_impersonated, get_current_teacher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/students", tags=["students"])


def _calculate_penalty(due_date) -> tuple[int, bool]:
    """Calculate penalty_pct and is_late based on due_date vs now."""
    now = _dt.utcnow()
    delta = now - due_date

    if delta.total_seconds() <= 0:
        penalty_pct = 100
    elif delta <= timedelta(hours=24):
        penalty_pct = 90
    elif delta <= timedelta(weeks=1):
        penalty_pct = 50
    else:
        penalty_pct = 10

    return penalty_pct, penalty_pct < 100


def _attendance_response(att) -> AttendanceResponse:
    """Build an AttendanceResponse from an Attendance ORM object."""
    return AttendanceResponse(
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


def _submission_response(submission) -> SubmissionResponse:
    """Build a SubmissionResponse from a Submission ORM object."""
    return SubmissionResponse(
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
        file_name=submission.file_name,
        file_size=submission.file_size,
        has_file=bool(submission.file_key),
        resubmit_count=submission.resubmit_count or 0,
    )


@router.get("/me", response_model=StudentResponse)
async def get_current_student_info(
    current_student: Student = Depends(get_student_or_impersonated)
):
    """Get current authenticated student's information."""
    return current_student


@router.get("/me/grades", response_model=List[GradeResponse])
async def get_student_grades(
    class_id: Optional[int] = None,
    current_student: Student = Depends(get_student_or_impersonated),
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
    current_student: Student = Depends(get_student_or_impersonated),
    db: Session = Depends(get_db)
):
    """Get current student's attendance records. Optionally filter by class."""
    query = db.query(Attendance).filter(
        Attendance.student_id == current_student.id
    )
    if class_id:
        query = query.filter(Attendance.class_id == class_id)
    records = query.all()
    return [_attendance_response(r) for r in records]


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
    current_student: Student = Depends(get_student_or_impersonated),
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
    current_student: Student = Depends(get_student_or_impersonated),
    db: Session = Depends(get_db)
):
    """Get grade calculation breakdown for a class using category weights."""
    enrollment = db.query(StudentClass).filter(
        StudentClass.student_id == current_student.id,
        StudentClass.class_id == class_id,
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="No estas inscrito en esta clase")

    # Grading mode
    class_ = db.query(Class).filter(Class.id == class_id).first()
    grading_mode = (class_.grading_mode if class_ and class_.grading_mode else None) or 'points'

    # Categories
    categories = db.query(GradeCategory).filter(
        GradeCategory.class_id == class_id
    ).all()

    # All grades for this student/class
    all_grades = db.query(Grade).filter(
        Grade.student_id == current_student.id,
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
                Submission.student_id == current_student.id,
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
        # If categories exist, uncategorized grades get remaining weight (or equal share)
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

    # Fallback if no categories and no uncategorized grades handled above
    if not categories and not uncategorized:
        valid = [g for g in all_grades if g.max_score and g.max_score > 0]
        weighted_sum = (sum((g.score / g.max_score) * 100 for g in valid) / len(valid)) if valid else 0.0

    # Participation — class-sourced (teacher-approved)
    class_part_pts = int(db.query(func.sum(Participation.points)).filter(
        Participation.student_id == current_student.id,
        Participation.class_id == class_id,
        Participation.approved == "approved",
    ).scalar() or 0)

    part_pts = class_part_pts  # kept for backward compat below
    part_contribution = float(class_part_pts)  # 1 tap = 1 grade point, no multiplier

    # Pending participation (submitted but not yet approved)
    pending_part_pts = int(db.query(func.sum(Participation.points)).filter(
        Participation.student_id == current_student.id,
        Participation.class_id == class_id,
        Participation.approved == "pending",
    ).scalar() or 0)

    # Special points
    sp_records = db.query(SpecialPoints).filter(
        SpecialPoints.student_id == current_student.id,
        SpecialPoints.class_id == class_id,
    ).all()
    sp_total = sum(sp.points_value for sp in sp_records if sp.opted_in and sp.awarded)

    sp_responses = [SpecialPointsResponse(
        id=sp.id, student_id=sp.student_id, class_id=sp.class_id,
        category=sp.category, opted_in=sp.opted_in, awarded=sp.awarded,
        points_value=sp.points_value, created_at=sp.created_at,
    ) for sp in sp_records]

    # Absence penalty: -1 per unjustified absence
    unjustified_absences = db.query(func.count(Attendance.id)).filter(
        Attendance.student_id == current_student.id,
        Attendance.class_id == class_id,
        Attendance.status == "absent",
    ).scalar() or 0
    absence_penalty = float(unjustified_absences)

    # Forum points: sum of casino points for this class's posts, PLUS any direct
    # penalty records (bonus_type='penalty') linked to this class via class_id.
    forum_pts_raw = db.query(func.sum(ForumPoints.points_earned)).filter(
        ForumPoints.user_id == current_student.id,
        or_(
            ForumPoints.post_id.in_(
                db.query(ForumPost.id).filter(ForumPost.class_id == class_id)
            ),
            (ForumPoints.class_id == class_id) & (ForumPoints.bonus_type == "penalty"),
        ),
    ).scalar() or 0.0
    forum_contribution = round(float(forum_pts_raw), 3)  # no cap — same as participation

    max_base_grade = sum(cat.weight for cat in categories) * 100
    final_grade = weighted_sum + part_contribution + sp_total + forum_contribution - absence_penalty
    if grading_mode == 'percentage':
        final_grade = min(100.0, final_grade)

    return {
        "student_id": current_student.id,
        "student_name": current_student.name,
        "student_email": current_student.email,
        "categories": [cb.model_dump() for cb in category_breakdowns],
        "participation_points": class_part_pts,
        "participation_points_class": class_part_pts,
        "pending_participation_points": pending_part_pts,
        "participation_points_forum": round(float(forum_pts_raw), 3),
        "participation_contribution": part_contribution,
        "special_points": [sp.model_dump() for sp in sp_responses],
        "special_points_total": sp_total,
        "absence_count": unjustified_absences,
        "absence_penalty": absence_penalty,
        "pending_justification_count": int(db.query(func.count(Attendance.id)).filter(
            Attendance.student_id == current_student.id,
            Attendance.class_id == class_id,
            Attendance.justification_status == "pending",
        ).scalar() or 0),
        "forum_points": forum_contribution,
        "final_grade": final_grade,
        "grading_mode": grading_mode,
        "max_base_grade": max_base_grade,
    }


@router.get("/me/assignments", response_model=list[AssignmentStudentView])
async def get_student_assignments(
    class_id: int,
    current_student: Student = Depends(get_student_or_impersonated),
    db: Session = Depends(get_db),
):
    """Get assignments for a class with the student's submission status."""
    assignments = db.query(Assignment).filter(
        Assignment.class_id == class_id,
        Assignment.published == True,
    ).order_by(Assignment.due_date.asc()).all()

    results = []
    for a in assignments:
        submission = db.query(Submission).filter(
            Submission.assignment_id == a.id,
            Submission.student_id == current_student.id,
            Submission.submitted_at.isnot(None),
        ).first()

        sub_response = None
        if submission:
            sub_response = _submission_response(submission)

        now = _dt.utcnow()
        is_active = (
            a.exam_type == 'online'
            and a.available_from is not None
            and a.available_from <= now
            and (a.available_until is None or now <= a.available_until)
        )

        results.append(AssignmentStudentView(
            id=a.id,
            class_id=a.class_id,
            title=a.title,
            description=a.description,
            due_date=a.due_date,
            max_points=a.max_points,
            allow_late=a.allow_late,
            exam_type=a.exam_type or 'homework',
            available_from=a.available_from,
            available_until=a.available_until,
            time_limit_min=a.time_limit_min,
            is_active=is_active,
            created_at=a.created_at,
            submission=sub_response,
        ))

    return results


@router.post("/me/assignments/{assignment_id}/submit", response_model=SubmissionResponse)
async def submit_assignment(
    assignment_id: int,
    data: SubmissionCreate,
    current_student: Student = Depends(get_student_or_impersonated),
    db: Session = Depends(get_db),
):
    """Submit an assignment."""
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id,
        Assignment.published == True,
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Reto no encontrado")

    # Verify student is enrolled
    enrollment = db.query(StudentClass).filter(
        StudentClass.student_id == current_student.id,
        StudentClass.class_id == assignment.class_id,
    ).first()
    if not enrollment:
        raise HTTPException(status_code=403, detail="No estas inscrito en esta clase")

    # Check for existing submission
    existing = db.query(Submission).filter(
        Submission.assignment_id == assignment_id,
        Submission.student_id == current_student.id,
    ).first()

    penalty_pct, is_late = _calculate_penalty(assignment.due_date)

    if existing:
        if existing.submitted_at is not None:
            raise HTTPException(status_code=400, detail="Ya enviaste este reto")
        # Re-submission: update the cleared row
        existing.drive_url = data.drive_url
        existing.submitted_at = _dt.utcnow()
        existing.is_late = is_late
        existing.penalty_pct = penalty_pct
        db.commit()
        db.refresh(existing)
        return _submission_response(existing)

    submission = Submission(
        assignment_id=assignment_id,
        student_id=current_student.id,
        drive_url=data.drive_url,
        is_late=is_late,
        penalty_pct=penalty_pct,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    return _submission_response(submission)


@router.post("/me/assignments/{assignment_id}/upload", response_model=SubmissionResponse)
async def upload_assignment_file(
    assignment_id: int,
    file: UploadFile = File(...),
    current_student: Student = Depends(get_student_or_impersonated),
    db: Session = Depends(get_db),
):
    """Upload a file for an assignment submission. Allows re-upload."""
    from app.storage import is_r2_configured, validate_file, upload_file, delete_file

    if not is_r2_configured():
        raise HTTPException(status_code=501, detail="Subida de archivos no configurada")

    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id,
        Assignment.published == True,
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Reto no encontrado")

    # Verify student is enrolled
    enrollment = db.query(StudentClass).filter(
        StudentClass.student_id == current_student.id,
        StudentClass.class_id == assignment.class_id,
    ).first()
    if not enrollment:
        raise HTTPException(status_code=403, detail="No estas inscrito en esta clase")

    # Read and validate file
    file_bytes = await file.read()
    error = validate_file(file.filename, len(file_bytes))
    if error:
        raise HTTPException(status_code=400, detail=error)

    # Generate R2 key
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "bin"
    timestamp = int(_dt.utcnow().timestamp())
    file_key = f"submissions/{current_student.id}_{assignment_id}_{timestamp}.{ext}"

    penalty_pct, is_late = _calculate_penalty(assignment.due_date)

    # Check for existing submission (allow re-upload / re-submission after delete)
    existing = db.query(Submission).filter(
        Submission.assignment_id == assignment_id,
        Submission.student_id == current_student.id,
    ).first()

    # Upload to R2
    upload_file(file_bytes, file_key, file.content_type or "application/octet-stream")

    if existing:
        # Delete old file if it had one
        if existing.file_key:
            delete_file(existing.file_key)
        existing.file_key = file_key
        existing.file_name = file.filename
        existing.file_size = len(file_bytes)
        existing.is_late = is_late
        existing.penalty_pct = penalty_pct
        existing.submitted_at = _dt.utcnow()
        db.commit()
        db.refresh(existing)
        return _submission_response(existing)
    else:
        submission = Submission(
            assignment_id=assignment_id,
            student_id=current_student.id,
            file_key=file_key,
            file_name=file.filename,
            file_size=len(file_bytes),
            is_late=is_late,
            penalty_pct=penalty_pct,
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
        return _submission_response(submission)


@router.get("/submissions/{submission_id}/file")
async def download_submission_file(
    submission_id: int,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Get a presigned download URL for a submission file."""
    from app.storage import is_r2_configured, generate_presigned_url

    if not is_r2_configured():
        raise HTTPException(status_code=501, detail="Subida de archivos no configurada")

    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Entrega no encontrada")

    if not submission.file_key:
        raise HTTPException(status_code=404, detail="Esta entrega no tiene archivo")

    # Auth: owner or teacher of the class
    assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id).first()
    is_owner = submission.student_id == current_student.id
    is_teacher = False
    if assignment:
        class_ = db.query(Class).filter(
            Class.id == assignment.class_id,
            Class.teacher_id == current_student.id,
        ).first()
        is_teacher = class_ is not None

    if not is_owner and not is_teacher:
        raise HTTPException(status_code=403, detail="No tienes permiso para ver este archivo")

    download_url = generate_presigned_url(submission.file_key)
    return {"download_url": download_url, "file_name": submission.file_name}


@router.delete("/submissions/{submission_id}")
async def delete_submission(
    submission_id: int,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Delete (clear) a submission. Only allowed if not yet graded."""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Entrega no encontrada")

    if submission.student_id != current_student.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para eliminar esta entrega")

    if submission.submitted_at is None:
        raise HTTPException(status_code=400, detail="Esta entrega ya fue eliminada")

    if submission.grade is not None:
        raise HTTPException(status_code=400, detail="No puedes eliminar una entrega ya calificada")

    # Delete R2 file if present
    if submission.file_key:
        from app.storage import is_r2_configured, delete_file
        if is_r2_configured():
            delete_file(submission.file_key)

    # Clear content but keep the row for resubmit tracking
    submission.drive_url = None
    submission.file_key = None
    submission.file_name = None
    submission.file_size = None
    submission.text_content = None
    submission.is_late = False
    submission.penalty_pct = 100
    submission.submitted_at = None
    submission.resubmit_count = (submission.resubmit_count or 0) + 1

    db.commit()

    return {"message": "Entrega eliminada"}


@router.post("/me/attendance/{attendance_id}/justify")
async def submit_justification(
    attendance_id: int,
    file: Optional[UploadFile] = File(None),
    justification_text: Optional[str] = Form(None),
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Submit a justification (text and/or file) for an absence."""
    has_text = justification_text and justification_text.strip()
    has_file = file and file.filename

    if not has_text and not has_file:
        raise HTTPException(status_code=400, detail="Debes escribir un motivo o adjuntar un documento")

    attendance = db.query(Attendance).filter(
        Attendance.id == attendance_id,
        Attendance.student_id == current_student.id,
    ).first()
    if not attendance:
        raise HTTPException(status_code=404, detail="Registro de asistencia no encontrado")

    if attendance.status not in ("absent", "late"):
        raise HTTPException(status_code=400, detail="Solo puedes justificar faltas o retardos")

    if attendance.justification_status == "approved":
        raise HTTPException(status_code=400, detail="Esta justificacion ya fue aprobada")

    if has_file:
        from app.storage import is_r2_configured, validate_file, upload_file, delete_file

        if not is_r2_configured():
            raise HTTPException(status_code=501, detail="Subida de archivos no configurada")

        file_bytes = await file.read()
        error = validate_file(file.filename, len(file_bytes))
        if error:
            raise HTTPException(status_code=400, detail=error)

        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "bin"
        timestamp = int(_dt.utcnow().timestamp())
        file_key = f"justifications/{current_student.id}_{attendance_id}_{timestamp}.{ext}"

        upload_file(file_bytes, file_key, file.content_type or "application/octet-stream")

        if attendance.justification_file_key:
            delete_file(attendance.justification_file_key)

        attendance.justification_file_key = file_key
        attendance.justification_file_name = file.filename

    attendance.justification_text = justification_text.strip() if has_text else attendance.justification_text
    attendance.justification_status = "pending"
    attendance.justification_submitted_at = _dt.utcnow()
    attendance.justification_reviewed_at = None
    attendance.justification_reviewed_by = None

    db.commit()
    db.refresh(attendance)

    return _attendance_response(attendance)


@router.get("/attendance/{attendance_id}/justification-file")
async def download_justification_file(
    attendance_id: int,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Get a presigned download URL for a justification file."""
    from app.storage import is_r2_configured, generate_presigned_url

    if not is_r2_configured():
        raise HTTPException(status_code=501, detail="Subida de archivos no configurada")

    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not attendance:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    if not attendance.justification_file_key:
        raise HTTPException(status_code=404, detail="No hay archivo de justificacion")

    # Auth: owner or teacher of the class
    is_owner = attendance.student_id == current_student.id
    is_teacher = False
    if attendance.class_id:
        class_ = db.query(Class).filter(
            Class.id == attendance.class_id,
            Class.teacher_id == current_student.id,
        ).first()
        is_teacher = class_ is not None

    if not is_owner and not is_teacher:
        raise HTTPException(status_code=403, detail="No tienes permiso para ver este archivo")

    download_url = generate_presigned_url(attendance.justification_file_key)
    return {"download_url": download_url, "file_name": attendance.justification_file_name}


# ── Online Exam Endpoints ──────────────────────────────────────────────


def _verify_exam_access(assignment_id: int, student, db):
    """Verify assignment exists, is online, and student is enrolled (or teacher owns it). Returns assignment."""
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id,
        Assignment.published == True,
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Examen no encontrado")
    if assignment.exam_type != 'online':
        raise HTTPException(status_code=400, detail="Este no es un examen online")

    # Teachers who own the class can access for preview
    if student.role == 'teacher':
        cls = db.query(Class).filter(
            Class.id == assignment.class_id,
            Class.teacher_id == student.id,
        ).first()
        if not cls:
            raise HTTPException(status_code=403, detail="No tienes acceso a este examen")
        return assignment

    # Students must be enrolled
    enrollment = db.query(StudentClass).filter(
        StudentClass.student_id == student.id,
        StudentClass.class_id == assignment.class_id,
    ).first()
    if not enrollment:
        raise HTTPException(status_code=403, detail="No estás inscrito en esta clase")
    return assignment


@router.get("/me/assignments/{assignment_id}/exam-status", response_model=ExamStatusResponse)
async def get_exam_status(
    assignment_id: int,
    current_student: Student = Depends(get_student_or_impersonated),
    db: Session = Depends(get_db),
):
    """Get online exam status: active window, time remaining, draft/submission state."""
    assignment = _verify_exam_access(assignment_id, current_student, db)

    # Teachers always get is_active=True (preview mode)
    is_preview = current_student.role == 'teacher'

    now = _dt.utcnow()
    is_active = is_preview or (
        assignment.available_from is not None
        and assignment.available_from <= now
        and (assignment.available_until is None or now <= assignment.available_until)
    )

    draft = db.query(OnlineExamDraft).filter(
        OnlineExamDraft.assignment_id == assignment_id,
        OnlineExamDraft.student_id == current_student.id,
    ).first()

    submission = db.query(Submission).filter(
        Submission.assignment_id == assignment_id,
        Submission.student_id == current_student.id,
        Submission.submitted_at.isnot(None),
    ).first()

    time_remaining = None
    if not is_preview and assignment.time_limit_min and draft:
        elapsed = (now - draft.started_at).total_seconds()
        time_remaining = max(0, int(assignment.time_limit_min * 60 - elapsed))

    return ExamStatusResponse(
        is_active=is_active,
        available_from=assignment.available_from,
        available_until=assignment.available_until,
        time_remaining_sec=time_remaining,
        draft_exists=draft is not None,
        draft_json=draft.draft_json if draft else None,
        submitted=False if is_preview else submission is not None,
        score=submission.grade if submission else None,
        is_preview=is_preview,
    )


@router.get("/me/assignments/{assignment_id}/exam-file")
async def get_exam_file(
    assignment_id: int,
    current_student: Student = Depends(get_student_or_impersonated),
    db: Session = Depends(get_db),
):
    """Get presigned URL for the online exam HTML file."""
    from app.storage import is_r2_configured, generate_presigned_url

    if not is_r2_configured():
        raise HTTPException(status_code=501, detail="Almacenamiento no configurado")

    assignment = _verify_exam_access(assignment_id, current_student, db)

    if not assignment.exam_html_key:
        raise HTTPException(status_code=404, detail="El examen no tiene archivo HTML cargado")

    url = generate_presigned_url(assignment.exam_html_key)
    return {"presigned_url": url}


@router.post("/me/assignments/{assignment_id}/exam-draft")
async def save_exam_draft(
    assignment_id: int,
    data: ExamDraftRequest,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Save or update draft state for an online exam."""
    assignment = _verify_exam_access(assignment_id, current_student, db)

    # Teachers in preview mode — no draft saved
    if current_student.role == 'teacher':
        return {"saved": True}

    now = _dt.utcnow()
    is_active = (
        assignment.available_from is not None
        and assignment.available_from <= now
        and (assignment.available_until is None or now <= assignment.available_until)
    )
    if not is_active:
        raise HTTPException(status_code=400, detail="El examen no está activo")

    # Check not already submitted
    existing_sub = db.query(Submission).filter(
        Submission.assignment_id == assignment_id,
        Submission.student_id == current_student.id,
        Submission.submitted_at.isnot(None),
    ).first()
    if existing_sub:
        raise HTTPException(status_code=400, detail="Ya entregaste este examen")

    # Upsert draft
    draft = db.query(OnlineExamDraft).filter(
        OnlineExamDraft.assignment_id == assignment_id,
        OnlineExamDraft.student_id == current_student.id,
    ).first()

    if draft:
        draft.draft_json = data.draft_json
        draft.saved_at = now
        # started_at is NOT updated — it stays at the first save
    else:
        draft = OnlineExamDraft(
            assignment_id=assignment_id,
            student_id=current_student.id,
            draft_json=data.draft_json,
            started_at=now,
            saved_at=now,
        )
        db.add(draft)

    db.commit()
    return {"saved": True}


@router.post("/me/assignments/{assignment_id}/submit-online-exam", response_model=OnlineExamSubmitResponse)
async def submit_online_exam(
    assignment_id: int,
    data: OnlineExamSubmitRequest,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Submit an online exam receipt and create the grade."""
    assignment = _verify_exam_access(assignment_id, current_student, db)

    # Teachers in preview mode — skip submission entirely
    if current_student.role == 'teacher':
        return OnlineExamSubmitResponse(
            score=data.total_score,
            max_points=assignment.max_points,
            grade_id=0,
            is_preview=True,
        )

    # Check window (allow a small grace period of 60s after closing)
    now = _dt.utcnow()
    if assignment.available_until and now > assignment.available_until + timedelta(seconds=60):
        raise HTTPException(status_code=400, detail="El periodo del examen ya cerró")

    # Check not already submitted
    existing_sub = db.query(Submission).filter(
        Submission.assignment_id == assignment_id,
        Submission.student_id == current_student.id,
        Submission.submitted_at.isnot(None),
    ).first()
    if existing_sub:
        raise HTTPException(status_code=400, detail="Ya entregaste este examen")

    # Create Submission
    submission = Submission(
        assignment_id=assignment_id,
        student_id=current_student.id,
        receipt_json=data.receipt_json,
        grade=data.total_score,
        submitted_at=_dt.utcnow(),
        is_late=False,
        penalty_pct=100,
    )
    db.add(submission)
    db.flush()

    # Upsert Grade (same pattern as in-person exam grading)
    existing_grade = db.query(Grade).filter(
        Grade.student_id == current_student.id,
        Grade.class_id == assignment.class_id,
        Grade.name == assignment.title,
    ).first()

    if existing_grade:
        existing_grade.score = data.total_score
        existing_grade.max_score = assignment.max_points
        existing_grade.category_id = assignment.category_id
        grade_obj = existing_grade
    else:
        grade_obj = Grade(
            student_id=current_student.id,
            class_id=assignment.class_id,
            category_id=assignment.category_id,
            name=assignment.title,
            score=data.total_score,
            max_score=assignment.max_points,
        )
        db.add(grade_obj)

    # Delete draft if exists
    db.query(OnlineExamDraft).filter(
        OnlineExamDraft.assignment_id == assignment_id,
        OnlineExamDraft.student_id == current_student.id,
    ).delete()

    db.commit()
    db.refresh(grade_obj)

    return OnlineExamSubmitResponse(
        score=data.total_score,
        max_points=assignment.max_points,
        grade_id=grade_obj.id,
    )
