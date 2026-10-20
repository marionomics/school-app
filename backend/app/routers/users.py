from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app import storage
from app.models import Class, Enrollment, User, utcnow
from app.schemas import UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


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
    user.avatar_key = key
    db.commit()
    db.refresh(user)
    return user


@router.delete("/me/avatar", response_model=UserOut)
def remove_my_avatar(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.avatar_key = None
    db.commit()
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
    target.avatar_key = None
    db.commit()
    db.refresh(target)
    return target
