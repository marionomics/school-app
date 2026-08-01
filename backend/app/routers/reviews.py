from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Class, Enrollment, Post, Review, User, utcnow
from app.routers.posts import _teacher_item
from app.schemas import ReviewIn, ReviewOut
from app.services.grades import lateness_score

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

SCALES = {"tarea": (Decimal("0"), Decimal("100")),
          "examen": (Decimal("1"), Decimal("10"))}


def _check_scale(item_type: str, score: Optional[Decimal]) -> None:
    if score is None:
        return
    low, high = SCALES[item_type]
    if not (low <= score <= high):
        raise HTTPException(
            status_code=422,
            detail=f"La calificación debe estar entre {low} y {high}")


@router.put("", response_model=ReviewOut)
def upsert_review(body: ReviewIn, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    item = _teacher_item(db, body.item_post_id, user)
    _check_scale(item.type, body.score)

    enrolled = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == body.student_id,
                Enrollment.class_id == item.class_id,
                Enrollment.status == "active")
        .first()
    )
    if enrolled is None:
        raise HTTPException(status_code=422,
                            detail="Ese alumno no está inscrito en la clase")

    auto = None
    if body.entrega_post_id is not None and item.due_date is not None:
        entrega = db.get(Post, body.entrega_post_id)
        if entrega is None or entrega.parent_id != item.id:
            raise HTTPException(status_code=422,
                                detail="Esa entrega no pertenece a esta tarea")
        auto = lateness_score(entrega.created_at, item.due_date)

    review = (
        db.query(Review)
        .filter(Review.item_post_id == item.id,
                Review.student_id == body.student_id)
        .first()
    )
    if review is None:
        review = Review(item_post_id=item.id, student_id=body.student_id)
        db.add(review)
    review.entrega_post_id = body.entrega_post_id
    review.score = body.score
    review.auto_score = auto
    review.feedback = body.feedback
    review.reviewer_id = user.id
    review.updated_at = utcnow()
    db.commit()
    db.refresh(review)
    return review
