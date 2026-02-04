"""
Google OAuth authentication module.
Verifies Google ID tokens and manages session tokens.
"""
import os
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from google.oauth2 import id_token
from google.auth.transport import requests
from sqlalchemy.orm import Session
from models.database import get_db
from models.models import Student

security = HTTPBearer(auto_error=False)

# In-memory session store: session_token -> student_id
sessions: dict[str, int] = {}

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")


def verify_google_token(token: str) -> dict:
    """
    Verify a Google ID token and return the decoded payload.
    Raises HTTPException if verification fails.
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth not configured (GOOGLE_CLIENT_ID missing)",
        )

    try:
        idinfo = id_token.verify_oauth2_token(
            token, requests.Request(), GOOGLE_CLIENT_ID
        )
        return idinfo
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def find_or_create_student(db: Session, google_info: dict) -> Student:
    """
    Find existing student by oauth_id or email, or create a new one.

    Priority:
    1. Match by oauth_id (Google's 'sub' claim)
    2. Match by email and link the account
    3. Create new student
    """
    oauth_id = google_info["sub"]
    email = google_info["email"]
    name = google_info.get("name", email.split("@")[0])

    # Try to find by oauth_id first
    student = db.query(Student).filter(Student.oauth_id == oauth_id).first()
    if student:
        return student

    # Try to find by email and link the account
    student = db.query(Student).filter(Student.email == email).first()
    if student:
        student.oauth_id = oauth_id
        db.commit()
        db.refresh(student)
        return student

    # Create new student
    student = Student(
        name=name,
        email=email,
        oauth_id=oauth_id,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def create_session(student_id: int) -> str:
    """Create a new session token for a student."""
    token = secrets.token_urlsafe(32)
    sessions[token] = student_id
    return token


def delete_session(token: str) -> bool:
    """Delete a session token. Returns True if it existed."""
    return sessions.pop(token, None) is not None


async def get_current_student(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Student:
    """
    Get the current authenticated student from the session token.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    student_id = sessions.get(token)

    if student_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        # Student was deleted, clean up session
        delete_session(token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Student not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return student
