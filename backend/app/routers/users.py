import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app import storage
from app.services import media
from app.models import Class, Enrollment, User, utcnow
from app.schemas import AuthorOut, UserOut, UserUpdate
from app.services.visibility import viewer_class_ids

router = APIRouter(prefix="/api/users", tags=["users"])


SEARCH_LIMIT = 8


def _like_prefix(term: str) -> str:
    # `_` and `%` are SQL wildcards; usernames contain `_`.
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@router.get("/search")
def search_users(q: str = Query(..., min_length=1, max_length=40),
                 user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """@mention autocomplete: anyone with a username (the feed is global),
    the viewer's classmates and teachers first."""
    term = q.strip().lstrip("@").lower()
    if not term:
        return {"users": []}
    like = _like_prefix(term)

    # Compute classmate ids before querying, so SQL can order with classmates first.
    mine = viewer_class_ids(db, user)
    if not mine:
        close = set()
    else:
        close = {uid for (uid,) in db.query(Enrollment.user_id).filter(
            Enrollment.class_id.in_(mine), Enrollment.status == "active")}
        close |= {tid for (tid,) in db.query(Class.teacher_id).filter(Class.id.in_(mine))}

    # Order in SQL: classmates first, then by username. Limit only SEARCH_LIMIT.
    if close:
        rows = (db.query(User)
                .filter(User.username.isnot(None), User.id != user.id,
                        or_(User.username.like(like, escape="\\"),
                            func.lower(User.name).like(like, escape="\\")))
                .order_by(User.id.in_(close).desc(), User.username)
                .limit(SEARCH_LIMIT).all())
    else:
        rows = (db.query(User)
                .filter(User.username.isnot(None), User.id != user.id,
                        or_(User.username.like(like, escape="\\"),
                            func.lower(User.name).like(like, escape="\\")))
                .order_by(User.username)
                .limit(SEARCH_LIMIT).all())
    return {"users": [AuthorOut.model_validate(u) for u in rows]}


@router.patch("/me", response_model=UserOut)
def update_me(
    body: UserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.username is not None and body.username != user.username:
        taken = db.query(User).filter(User.username == body.username).first()
        if taken is not None:
            raise HTTPException(status_code=409, detail="Ese username ya está ocupado")
        user.username = body.username
    if body.bio is not None:
        user.bio = body.bio
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ese username ya está ocupado")
    db.refresh(user)
    return user


@router.get("/username-available")
def username_available(
    u: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exists = db.query(User).filter(User.username == u).first() is not None
    return {"available": not exists}


AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}

logger = logging.getLogger(__name__)


def _delete_avatar_file(key: Optional[str]) -> None:
    """A removed or replaced profile photo is deleted from R2, not just
    unlinked — for a moderation removal the photo must actually be gone
    (Mario, 2026-10-20). Runs after the commit and never fails the request:
    the user already sees the change; a leftover object is only storage."""
    if not key:
        return
    media.forget(key)
    try:
        storage.delete_object(key)
    except Exception:
        logger.exception("Could not delete avatar %s from R2", key)


@router.put("/me/avatar", response_model=UserOut)
def upload_avatar(file: UploadFile = File(...), user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    if not storage.is_r2_configured():
        raise HTTPException(status_code=400, detail="La subida de archivos no está habilitada")
    data = file.file.read()
    if file.content_type not in AVATAR_TYPES:
        raise HTTPException(status_code=422, detail="La foto debe ser JPG, PNG o WebP")
    if len(data) > storage.MAX_FILE_SIZE:
        raise HTTPException(status_code=422, detail="La foto es demasiado grande (máximo 10 MB)")
    key = f"avatars/{user.id}_{int(utcnow().timestamp())}.jpg"
    storage.upload_bytes(data, key, file.content_type)
    previous = user.avatar_key
    user.avatar_key = key
    db.commit()
    _delete_avatar_file(previous)
    db.refresh(user)
    return user


@router.delete("/me/avatar", response_model=UserOut)
def remove_my_avatar(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    previous = user.avatar_key
    user.avatar_key = None
    db.commit()
    _delete_avatar_file(previous)
    db.refresh(user)
    return user


@router.delete("/{user_id}/avatar", response_model=UserOut)
def remove_avatar(user_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """The teacher steps in for the exception — no approval queue. The student
    goes back to their Google photo and can upload another."""
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Sólo el profesor puede quitar una foto")
    in_my_class = (
        db.query(Enrollment)
        .join(Class, Class.id == Enrollment.class_id)
        .filter(Enrollment.user_id == user_id, Class.teacher_id == user.id)
        .first()
    )
    if in_my_class is None:
        raise HTTPException(status_code=403, detail="Ese alumno no está en tus clases")
    target = db.get(User, user_id)
    previous = target.avatar_key
    target.avatar_key = None
    db.commit()
    _delete_avatar_file(previous)
    db.refresh(target)
    return target
