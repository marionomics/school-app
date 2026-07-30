"""The ONLY module allowed to write points_ledger rows."""
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Enrollment, Like, Post, PointsLedger, User, utcnow

TAP_VALUE = Decimal("1.0")
LIKE_VALUE = Decimal("1.0")


def _recipient_can_earn(db: Session, user_id: int, class_id: Optional[int]) -> bool:
    if class_id is None:
        return False
    user = db.get(User, user_id)
    if user is None or user.role == "teacher":
        return False
    enrollment = (
        db.query(Enrollment)
        .filter(
            Enrollment.user_id == user_id,
            Enrollment.class_id == class_id,
            Enrollment.status == "active",
        )
        .first()
    )
    return enrollment is not None


def award(db: Session, *, user_id: int, class_id: Optional[int], source_type: str,
          source_id: int, points: Decimal, note: Optional[str] = None) -> Optional[PointsLedger]:
    if not _recipient_can_earn(db, user_id, class_id):
        return None
    existing = (
        db.query(PointsLedger)
        .filter(
            PointsLedger.source_type == source_type,
            PointsLedger.source_id == source_id,
            PointsLedger.revoked_at.is_(None),
        )
        .first()
    )
    if existing is not None:
        return existing
    row = PointsLedger(user_id=user_id, class_id=class_id, source_type=source_type,
                       source_id=source_id, points=points, note=note)
    db.add(row)
    db.flush()
    return row


def revoke_for_source(db: Session, *, source_type: str, source_id: int, revoked_by: int) -> int:
    rows = (
        db.query(PointsLedger)
        .filter(
            PointsLedger.source_type == source_type,
            PointsLedger.source_id == source_id,
            PointsLedger.revoked_at.is_(None),
        )
        .all()
    )
    for row in rows:
        row.revoked_at = utcnow()
        row.revoked_by = revoked_by
    db.flush()
    return len(rows)


def award_participacion(db: Session, post: Post) -> Optional[PointsLedger]:
    if post.type != "participacion" or not post.taps:
        return None
    return award(db, user_id=post.author_id, class_id=post.class_id,
                 source_type="participacion", source_id=post.id,
                 points=TAP_VALUE * post.taps)


def award_like(db: Session, *, like: Like, post: Post, liker: User) -> Optional[PointsLedger]:
    if liker.role == "teacher":
        return None
    return award(db, user_id=post.author_id, class_id=post.class_id,
                 source_type="forum_like", source_id=like.id, points=LIKE_VALUE)


def revoke_like(db: Session, *, like_id: int, revoked_by: int) -> int:
    return revoke_for_source(db, source_type="forum_like", source_id=like_id,
                             revoked_by=revoked_by)


def revoke_post(db: Session, *, post: Post, revoked_by: int) -> int:
    n = revoke_for_source(db, source_type="participacion", source_id=post.id,
                          revoked_by=revoked_by)
    like_ids = [lid for (lid,) in db.query(Like.id).filter(Like.post_id == post.id).all()]
    for lid in like_ids:
        n += revoke_for_source(db, source_type="forum_like", source_id=lid,
                               revoked_by=revoked_by)
    return n
