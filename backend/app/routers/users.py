from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import User
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
    db.commit()
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
