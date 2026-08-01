from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Class, Enrollment, Post, PointsLedger, Review, User
from app.services.grades import _counting_entrega, counting_review, lateness_score

router = APIRouter(prefix="/api/review", tags=["review"])


def _owned_class(db: Session, class_id: int, user: User) -> Class:
    klass = db.get(Class, class_id)
    if klass is None:
        raise HTTPException(status_code=404, detail="Clase no encontrada")
    if user.role != "teacher" or klass.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="No eres profesor de esa clase")
    return klass


def _student_json(u: User) -> dict:
    return {"id": u.id, "username": u.username, "name": u.name}


def _active_students(db: Session, class_id: int) -> list:
    rows = (
        db.query(User)
        .join(Enrollment, Enrollment.user_id == User.id)
        .filter(Enrollment.class_id == class_id, Enrollment.status == "active")
        .all()
    )
    return sorted(rows, key=lambda u: (u.username or "", u.id))


@router.get("/entregas")
def entregas_queue(class_id: int, status: str = Query("unopened"),
                   user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    klass = _owned_class(db, class_id, user)
    tareas = (
        db.query(Post)
        .filter(Post.class_id == klass.id, Post.type == "tarea", Post.status == "active")
        .order_by(Post.due_date.desc())
        .all()
    )
    groups = []
    for tarea in tareas:
        entregas = []
        for student in _active_students(db, klass.id):
            entrega = _counting_entrega(db, student.id, tarea.id)
            if entrega is None:
                continue
            review = counting_review(db, tarea.id, student.id, entrega)
            reviewed = review is not None
            if status == "unopened" and reviewed:
                continue
            auto = (lateness_score(entrega.created_at, tarea.due_date)
                    if tarea.due_date is not None else None)
            entregas.append({
                "student": _student_json(student),
                "entrega_post_id": entrega.id,
                "created_at": entrega.created_at,
                "auto_score": float(auto) if auto is not None else None,
                "reviewed": reviewed,
                "score": float(review.score) if reviewed and review.score is not None else None,
            })
        if not entregas:
            continue
        groups.append({
            "tarea": {"id": tarea.id, "content": tarea.content, "due_date": tarea.due_date},
            "pending": sum(1 for e in entregas if not e["reviewed"]),
            "entregas": entregas,
        })
    return {"groups": groups}


@router.get("/examenes")
def examenes_list(class_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    klass = _owned_class(db, class_id, user)
    rows = (
        db.query(Post)
        .filter(Post.class_id == klass.id, Post.type == "examen",
                Post.status == "active")
        .order_by(Post.created_at.desc())
        .all()
    )
    return {"items": [{"id": p.id, "content": p.content,
                       "examen_mode": p.examen_mode, "graded_at": p.graded_at,
                       "created_at": p.created_at} for p in rows]}


@router.get("/examenes/{examen_id}")
def examen_roster(examen_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    examen = db.get(Post, examen_id)
    if examen is None or examen.type != "examen":
        raise HTTPException(status_code=404, detail="Examen no encontrado")
    _owned_class(db, examen.class_id, user)
    rows = []
    for student in _active_students(db, examen.class_id):
        entrega = _counting_entrega(db, student.id, examen.id)
        review = (
            db.query(Review)
            .filter(Review.item_post_id == examen.id, Review.student_id == student.id)
            .first()
        )
        rows.append({
            "student": _student_json(student),
            "entrega_post_id": entrega.id if entrega else None,
            "score": float(review.score) if review and review.score is not None else None,
        })
    return {"examen": {"id": examen.id, "content": examen.content,
                       "examen_mode": examen.examen_mode, "graded_at": examen.graded_at},
            "rows": rows}


@router.get("/participaciones")
def participaciones(class_id: int, limit: int = Query(50, ge=1, le=200),
                    user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    klass = _owned_class(db, class_id, user)
    posts = (
        db.query(Post)
        .filter(Post.class_id == klass.id, Post.type == "participacion")
        .order_by(Post.created_at.desc())
        .limit(limit)
        .all()
    )
    items = []
    for p in posts:
        row = (
            db.query(PointsLedger)
            .filter(PointsLedger.source_type == "participacion",
                    PointsLedger.source_id == p.id)
            .first()
        )
        items.append({
            "post_id": p.id,
            "student": _student_json(p.author),
            "content": p.content,
            "taps": p.taps,
            "points": float(row.points) if row is not None else 0.0,
            "vetoed": p.status == "vetoed",
            "veto_reason": p.veto_reason,
            "created_at": p.created_at,
        })
    return {"items": items}
