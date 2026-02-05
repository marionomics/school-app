from pydantic import BaseModel, EmailStr
from datetime import datetime, date
from typing import Optional, List


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
    role: str = "student"
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
    class_id: int


class ParticipationResponse(BaseModel):
    id: int
    student_id: int
    date: date
    description: str
    points: int
    approved: str = "pending"

    class Config:
        from_attributes = True


# Grade schemas
class GradeCreate(BaseModel):
    student_id: int
    class_id: int
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


# Admin schemas
class BulkAttendanceItem(BaseModel):
    student_id: int
    status: str  # present, absent, late, excused
    notes: Optional[str] = None


class BulkAttendanceCreate(BaseModel):
    date: Optional[date] = None
    class_id: int
    records: list[BulkAttendanceItem]


class ParticipationUpdate(BaseModel):
    approved: str  # pending, approved, rejected
    points: Optional[int] = None


class ParticipationWithStudent(ParticipationResponse):
    student_name: str
    student_email: str


# Class schemas
class ClassCreate(BaseModel):
    name: str
    code_prefix: Optional[str] = None


class ClassResponse(BaseModel):
    id: int
    name: str
    code: str
    teacher_id: int
    created_at: datetime
    student_count: Optional[int] = 0

    class Config:
        from_attributes = True


class JoinClassRequest(BaseModel):
    code: str


class StudentClassResponse(BaseModel):
    id: int
    class_id: int
    class_name: str
    class_code: str
    joined_at: datetime

    class Config:
        from_attributes = True


class ClassWithStudents(ClassResponse):
    students: List[StudentResponse] = []
