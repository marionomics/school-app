from sqlalchemy.orm import Session

from app.models import Class, Like, Post, User, utcnow


def _validates(db: Session, post: Post, teacher: User) -> bool:
    """Only a participación in a class this teacher owns is validated by
    their aura. Anywhere else the aura is just aura."""
    if post.type != "participacion" or post.class_id is None:
        return False
    klass = db.get(Class, post.class_id)
    return klass is not None and klass.teacher_id == teacher.id


def set_teacher_aura(db: Session, post: Post, teacher: User, on: bool) -> None:
    """The teacher's aura and validation are one fact, stored in two places:
    the like row and posts.reviewed_at. This is the only writer of both, so
    they cannot drift apart.

    Moves no points (a teacher's like never earned any — award_like) and never
    touches last_activity_at. Idempotent. Does not commit: the caller does,
    so the bulk endpoint stays all-or-nothing.
    """
    existing = (
        db.query(Like)
        .filter(Like.user_id == teacher.id, Like.post_id == post.id)
        .first()
    )
    if on and existing is None and post.author_id != teacher.id:
        db.add(Like(user_id=teacher.id, post_id=post.id))
        post.like_count += 1
    elif not on and existing is not None:
        db.delete(existing)
        post.like_count = max(0, post.like_count - 1)

    if not _validates(db, post, teacher):
        return
    if on:
        if post.reviewed_at is None:      # keep the first time it was seen
            post.reviewed_at = utcnow()
            post.reviewed_by = teacher.id
    else:
        post.reviewed_at = None
        post.reviewed_by = None
