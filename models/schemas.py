from pydantic import BaseModel, EmailStr
from datetime import datetime, date as date_type
from typing import Optional, List, Union


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
    date: Optional[date_type] = None
    status: str  # present, absent, late, excused
    notes: Optional[str] = None


class AttendanceResponse(BaseModel):
    id: int
    student_id: int
    date: date_type
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
    date: date_type
    description: str
    points: int
    approved: str = "pending"

    class Config:
        from_attributes = True


# Grade schemas
class GradeCreate(BaseModel):
    student_id: int
    class_id: int
    category_id: Optional[int] = None
    category: Optional[str] = None  # legacy string field
    name: Optional[str] = None  # e.g., "Reto Semana 1"
    score: float
    max_score: float
    date: Optional[date_type] = None


class GradeResponse(BaseModel):
    id: int
    student_id: int
    category_id: Optional[int] = None
    category: Optional[str] = None
    name: Optional[str] = None
    score: float
    max_score: float
    date: date_type

    class Config:
        from_attributes = True


# Grade Category schemas
class GradeCategoryCreate(BaseModel):
    name: str
    weight: float  # Percentage as decimal (0.4 = 40%)


class GradeCategoryResponse(BaseModel):
    id: int
    class_id: int
    name: str
    weight: float
    created_at: datetime

    class Config:
        from_attributes = True


class GradeCategoryUpdate(BaseModel):
    name: Optional[str] = None
    weight: Optional[float] = None


# Special Points schemas
class SpecialPointsCreate(BaseModel):
    category: str  # "english" or "notebook"
    opted_in: bool = True


class SpecialPointsResponse(BaseModel):
    id: int
    student_id: int
    class_id: int
    category: str
    opted_in: bool
    awarded: bool
    points_value: float
    created_at: datetime

    class Config:
        from_attributes = True


class SpecialPointsUpdate(BaseModel):
    opted_in: Optional[bool] = None
    awarded: Optional[bool] = None


# Grade calculation schemas
class CategoryGradeBreakdown(BaseModel):
    category_id: int
    category_name: str
    weight: float
    grades: List[GradeResponse]
    average: float  # Average percentage for this category
    weighted_contribution: float  # weight * average


class StudentGradeCalculation(BaseModel):
    student_id: int
    student_name: str
    student_email: str
    categories: List[CategoryGradeBreakdown]
    participation_points: int
    participation_contribution: float  # 0.1 * approved points
    special_points: List[SpecialPointsResponse]
    special_points_total: float
    final_grade: float  # Sum of all contributions


class StudentRosterEntry(BaseModel):
    student: StudentResponse
    attendance_rate: float
    participation_points: int
    grade_breakdown: List[CategoryGradeBreakdown]
    special_points: List[SpecialPointsResponse]
    final_grade: float


# Admin schemas
class BulkAttendanceItem(BaseModel):
    student_id: int
    status: str  # present, absent, late, excused
    notes: Optional[str] = None


class BulkAttendanceCreate(BaseModel):
    date: Optional[date_type] = None
    class_id: int
    records: List[BulkAttendanceItem]


class ParticipationUpdate(BaseModel):
    approved: str  # pending, approved, rejected
    points: Optional[int] = None


class BulkParticipationItem(BaseModel):
    id: int
    points: Optional[int] = None


class BulkParticipationApprove(BaseModel):
    class_id: int
    items: List[BulkParticipationItem]


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


# Dashboard schemas
class StudentDashboardEntry(BaseModel):
    id: int
    name: str
    email: str
    attendance_rate: float  # 0-100
    attendance_present: int
    attendance_total: int
    participation_points: int
    participation_pending: int
    average_grade: float
    final_grade: float
    last_activity: Optional[datetime] = None
    status: str  # "good", "warning", "at_risk"

    class Config:
        from_attributes = True


class ClassDashboardStats(BaseModel):
    class_id: int
    class_name: str
    class_code: str
    total_students: int
    overall_attendance_rate: float
    average_grade: float
    pending_participation: int
    students_at_risk: int
    top_performers: int
    categories: List[GradeCategoryResponse]


class ClassDashboardResponse(BaseModel):
    stats: ClassDashboardStats
    students: List[StudentDashboardEntry]
    recent_activity: List[dict]  # Recent attendance, grades, participation


# Assignment schemas
class AssignmentCreate(BaseModel):
    class_id: int
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    max_points: Optional[float] = 100


class SubmissionResponse(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    text_content: Optional[str] = None
    submitted_at: datetime
    is_late: bool
    grade: Optional[float] = None
    feedback: Optional[str] = None
    graded_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AssignmentResponse(BaseModel):
    id: int
    class_id: int
    category_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    due_date: datetime
    max_points: float
    allow_late: bool
    published: bool
    created_at: datetime
    submission_count: int = 0
    graded_count: int = 0

    class Config:
        from_attributes = True


class AssignmentStudentView(BaseModel):
    id: int
    class_id: int
    title: str
    description: Optional[str] = None
    due_date: datetime
    max_points: float
    allow_late: bool
    created_at: datetime
    submission: Optional[SubmissionResponse] = None

    class Config:
        from_attributes = True


class SubmissionCreate(BaseModel):
    text_content: Optional[str] = None
