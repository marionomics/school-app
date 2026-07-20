from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuthSession, User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticado")
    token = header.removeprefix("Bearer ")
    session = db.query(AuthSession).filter(AuthSession.token == token).first()
    if session is None:
        raise HTTPException(status_code=401, detail="Sesión inválida")
    expires = session.expires_at
    if expires.tzinfo is None:  # SQLite drops tzinfo
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Sesión expirada")
    return session.user


def get_current_teacher(user: User = Depends(get_current_user)) -> User:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Solo para el profesor")
    return user
