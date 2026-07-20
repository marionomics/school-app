from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.google import verify_google_token
from app.auth.sessions import create_session, revoke_session
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import AuthResponse, GoogleLoginRequest, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/google", response_model=AuthResponse)
def login_google(body: GoogleLoginRequest, db: Session = Depends(get_db)):
    try:
        info = verify_google_token(body.credential)
    except ValueError:
        raise HTTPException(status_code=401, detail="Token de Google inválido")

    user = db.query(User).filter(User.google_id == info["sub"]).first()
    if user is None:
        user = User(
            google_id=info["sub"],
            email=info["email"],
            name=info["name"],
            avatar_url=info.get("picture"),
        )
        db.add(user)
    if settings.teacher_email and info["email"] == settings.teacher_email:
        user.role = "teacher"
    db.commit()
    db.refresh(user)
    token = create_session(db, user)
    return AuthResponse(
        token=token, user=UserOut.model_validate(user), needs_onboarding=user.username is None
    )


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)):
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        revoke_session(db, header.removeprefix("Bearer "))
