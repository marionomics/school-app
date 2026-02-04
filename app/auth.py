"""
Placeholder authentication module.
This will be replaced with proper OAuth implementation later.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from models.database import get_db
from models.models import Student

security = HTTPBearer(auto_error=False)


async def get_current_student(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Student:
    """
    Placeholder authentication.
    For now, accepts any token in format 'student_<id>' and returns that student.
    Example: Authorization: Bearer student_1

    TODO: Replace with proper OAuth implementation
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Placeholder: parse student ID from token
    if token.startswith("student_"):
        try:
            student_id = int(token.split("_")[1])
            student = db.query(Student).filter(Student.id == student_id).first()
            if student:
                return student
        except (ValueError, IndexError):
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
