from pydantic import BaseModel, EmailStr
from datetime import datetime, date
from typing import Optional


# Student schemas
class StudentCreate(BaseModel):
    name: str
    email: EmailStr
    oauth_id: Optional[str] = None


class StudentResponse(BaseModel):
    id: int
    name: str
    email: str
    oauth_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Attendance schemas
class AttendanceCreate(BaseModel):
    student_id: int
    date: Optional[date] = None
    status: str  # present, absent, late, excused
    notes: Optional[str] = None


class AttendanceResponse(BaseModel):
    id: int
    student_id: int
    date: date
    status: str
    notes: Optional[str] = None

    class Config:
        from_attributes = True


# Participation schemas
class ParticipationCreate(BaseModel):
    description: str
    points: Optional[int] = 1


class ParticipationResponse(BaseModel):
    id: int
    student_id: int
    date: date
    description: str
    points: int

    class Config:
        from_attributes = True


# Grade schemas
class GradeCreate(BaseModel):
    student_id: int
    category: str
    score: float
    max_score: float
    date: Optional[date] = None


class GradeResponse(BaseModel):
    id: int
    student_id: int
    category: str
    score: float
    max_score: float
    date: date

    class Config:
        from_attributes = True
