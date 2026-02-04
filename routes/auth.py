"""
Authentication routes for Google OAuth.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database import get_db
from models.schemas import StudentResponse
from app.auth import (
    verify_google_token,
    find_or_create_student,
    create_session,
    delete_session,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


class GoogleAuthRequest(BaseModel):
    credential: str


class AuthResponse(BaseModel):
    token: str
    student: StudentResponse


@router.post("/google", response_model=AuthResponse)
async def google_auth(request: GoogleAuthRequest, db: Session = Depends(get_db)):
    """
    Authenticate with Google OAuth.
    Accepts a Google ID token, verifies it, and returns a session token.
    """
    # Verify the Google token
    google_info = verify_google_token(request.credential)

    # Find or create the student
    student = find_or_create_student(db, google_info)

    # Create a session
    session_token = create_session(student.id)

    return AuthResponse(
        token=session_token,
        student=StudentResponse.model_validate(student),
    )


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Log out the current user by invalidating their session token.
    """
    if credentials:
        delete_session(credentials.credentials)

    return {"message": "Logged out successfully"}
