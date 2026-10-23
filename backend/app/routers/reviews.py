from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Class, Enrollment, Post, Review, User, utcnow
from app.routers.posts import _teacher_item
from app.schemas import AcceptSuggestedIn, ReviewIn, ReviewOut
from app.services.grades import _counting_entrega, counting_review, lateness_score

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


@router.post("/accept-suggested")
def accept_suggested(body: AcceptSuggestedIn, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """Grade every entrega sent with its suggested (lateness) score, in one tap.

    Moves no grade — an ungraded entrega already counts with that score — it
    only turns "suggested" into "given", which clears the teacher's pending
    list. Exactly the ids sent: an entrega that arrived after the teacher
    looked must not be graded unseen. Never overwrites a grade already given;
    a replaced entrega or one from an inactive student is skipped. An id that
    is not an entrega of this tarea rejects the whole batch.
    """
    item = _teacher_item(db, body.item_post_id, user)
    if item.type != "tarea" or item.due_date is None:
        raise HTTPException(status_code=422, detail="Esta tarea no tiene calificación sugerida")
    entregas = (db.query(Post).filter(Post.id.in_(body.entrega_post_ids)).all()
                if body.entrega_post_ids else [])
    if (len(entregas) != len(set(body.entrega_post_ids))
            or any(e.parent_id != item.id or not e.is_entrega for e in entregas)):
        raise HTTPException(status_code=422, detail="Esa entrega no pertenece a esta tarea")

    active = {uid for (uid,) in db.query(Enrollment.user_id).filter(
        Enrollment.class_id == item.class_id, Enrollment.status == "active")}
    graded = 0
    for e in entregas:
        if e.author_id not in active:
            continue
        counting = _counting_entrega(db, e.author_id, item.id)
        if counting is None or counting.id != e.id:
            continue
        if counting_review(db, item.id, e.author_id, counting) is not None:
            continue
        auto = lateness_score(e.created_at, item.due_date)
        review = (db.query(Review)
                  .filter(Review.item_post_id == item.id, Review.student_id == e.author_id)
                  .first())
        if review is None:
            review = Review(item_post_id=item.id, student_id=e.author_id)
            db.add(review)
        review.entrega_post_id = e.id
        review.score = auto
        review.auto_score = auto
        review.feedback = None
        review.reviewer_id = user.id
        review.updated_at = utcnow()
        graded += 1
    db.commit()
    return {"graded": graded}
