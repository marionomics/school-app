from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_teacher
from app.database import get_db
from app.models import AttendanceRecord, Class, ClassSession, User, utcnow
from app.schemas import AttendancePut, SessionOut

router = APIRouter(tags=["attendance"])


def _owned_class(db: Session, class_id: int, teacher: User) -> Class:
    klass = db.get(Class, class_id)
    if klass is None:
        raise HTTPException(status_code=404, detail="Clase no encontrada")
    if klass.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="No eres profesor de esa clase")
    return klass


def _owned_session(db: Session, class_id: int, session_id: int,
                   teacher: User) -> ClassSession:
    _owned_class(db, class_id, teacher)
    session = db.get(ClassSession, session_id)
    if session is None or session.class_id != class_id:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return session


def _attendance_count(db: Session, session_id: int) -> int:
    return (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.session_id == session_id)
        .count()
    )


def _to_out(db: Session, s: ClassSession) -> SessionOut:
    return SessionOut(
        id=s.id,
        class_id=s.class_id,
        date=s.date,
        opened_at=s.opened_at,
        closed_at=s.closed_at,
        attendance_count=_attendance_count(db, s.id),
    )


@router.post("/api/classes/{class_id}/sessions", status_code=201,
             response_model=SessionOut)
def open_session(
    class_id: int,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    _owned_class(db, class_id, teacher)
    today = date_type.today()
    existing = (
        db.query(ClassSession)
        .filter(ClassSession.class_id == class_id,
                ClassSession.date == today,
                ClassSession.closed_at.is_(None))
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=409,
                            detail="Ya hay una sesión abierta para hoy")
    session = ClassSession(class_id=class_id, date=today, opened_at=utcnow())
    db.add(session)
    db.commit()
    db.refresh(session)
    return _to_out(db, session)


@router.delete("/api/classes/{class_id}/sessions/{session_id}", status_code=204)
def close_session(
    class_id: int,
    session_id: int,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    session = _owned_session(db, class_id, session_id, teacher)
    session.closed_at = utcnow()
    db.commit()


# NOTE: active_session must be registered before any {session_id} route to
# avoid FastAPI's path parameter matching "active" as a session ID.
@router.get("/api/classes/{class_id}/sessions/active")
def active_session(
    class_id: int,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    _owned_class(db, class_id, teacher)
    session = (
        db.query(ClassSession)
        .filter(ClassSession.class_id == class_id,
                ClassSession.closed_at.is_(None))
        .order_by(ClassSession.opened_at.desc())
        .first()
    )
    if session is None:
        return None
    return _to_out(db, session)


@router.get("/api/classes/{class_id}/sessions")
def list_sessions(
    class_id: int,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    _owned_class(db, class_id, teacher)
    sessions = (
        db.query(ClassSession)
        .filter(ClassSession.class_id == class_id)
        .order_by(ClassSession.date.desc(), ClassSession.opened_at.desc())
        .all()
    )
    return {"sessions": [_to_out(db, s) for s in sessions]}


@router.put("/api/sessions/{session_id}/attendance")
def put_attendance(
    session_id: int,
    body: AttendancePut,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    session = db.get(ClassSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    _owned_class(db, session.class_id, teacher)

    db.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == session_id
    ).delete()

    for rec in body.records:
        db.add(AttendanceRecord(
            session_id=session_id,
            user_id=rec.user_id,
            status=rec.status,
        ))
    db.commit()
    return {"saved": len(body.records)}
