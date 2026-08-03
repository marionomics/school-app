from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional



from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    username: Optional[str]
    bio: str
    avatar_url: Optional[str]
    role: str
    grade_is_private: bool


class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, pattern=r"^[a-z0-9_]{3,20}$")
    bio: Optional[str] = Field(default=None, max_length=500)


class GoogleLoginRequest(BaseModel):
    credential: str


class AuthResponse(BaseModel):
    token: str
    user: UserOut
    needs_onboarding: bool


class ScheduleBlock(BaseModel):
    day: int = Field(ge=0, le=6)  # 0 = lunes
    start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code_prefix: str = Field(default="CLASE", max_length=10)
    start_date: date
    end_date: date
    schedule: List[ScheduleBlock] = []
    tareas_weight: int = Field(default=30, ge=0, le=100)
    examenes_weight: int = Field(default=30, ge=0, le=100)


class ClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    teacher_id: int
    start_date: date
    end_date: date
    schedule: List[ScheduleBlock] = Field(validation_alias="schedule_json")
    tareas_weight: int
    examenes_weight: int
    attendance_required_pct: int


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    username: Optional[str]
    avatar_url: Optional[str]
    status: str


class ClassDetail(ClassOut):
    members: List[MemberOut] = []


class JoinRequest(BaseModel):
    code: str


class MyClasses(BaseModel):
    teaching: List[ClassOut]
    enrolled: List[ClassOut]


class AuthorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: Optional[str]
    name: str
    avatar_url: Optional[str]
    role: str


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    mime_type: str


class ReviewIn(BaseModel):
    item_post_id: int
    student_id: int
    entrega_post_id: Optional[int] = None
    score: Optional[Decimal] = None
    feedback: Optional[str] = None


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_post_id: int
    student_id: int
    entrega_post_id: Optional[int]
    score: Optional[Decimal]
    auto_score: Optional[Decimal]
    feedback: Optional[str]
    updated_at: Optional[datetime]


class IncentiveCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    points: Decimal = Field(gt=0)
    description: Optional[str] = None


class IncentiveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    class_id: int
    name: str
    points: Decimal
    description: Optional[str]
    created_at: datetime
    deleted_at: Optional[datetime]


class AwardBody(BaseModel):
    student_id: int


class LedgerRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    class_id: Optional[int]
    source_type: str
    source_id: int
    points: Decimal
    note: Optional[str]
    created_at: datetime


class ClassSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tareas_weight: Optional[int] = Field(default=None, ge=0, le=100)
    examenes_weight: Optional[int] = Field(default=None, ge=0, le=100)
    tap_value: Optional[Decimal] = Field(default=None, gt=0)
    like_value: Optional[Decimal] = Field(default=None, gt=0)
    like_exponent: Optional[Decimal] = Field(default=None, ge=Decimal("0.1"), le=Decimal("2.0"))
    attendance_required_pct: Optional[int] = Field(default=None, ge=0, le=100)


class ClassSettingsOut(BaseModel):
    tareas_weight: int
    examenes_weight: int
    tap_value: Decimal
    like_value: Decimal
    like_exponent: Decimal
    attendance_required_pct: int


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    class_id: int
    date: date
    opened_at: Optional[datetime]
    closed_at: Optional[datetime]
    attendance_count: int = 0


class AttendanceRecordIn(BaseModel):
    user_id: int
    status: str  # present|absent|late


class AttendancePut(BaseModel):
    records: List[AttendanceRecordIn]


class RosterStudent(BaseModel):
    id: int
    name: str
    username: Optional[str]
    avatar_url: Optional[str]
    status: str  # active|ghost|polizon
    grade: float
    faltas: int


class PostOut(BaseModel):
    id: int
    author: AuthorOut
    type: str
    class_id: Optional[int]
    class_name: Optional[str]
    content: str
    taps: Optional[int]
    due_date: Optional[datetime] = None
    is_entrega: bool = False
    examen_mode: Optional[str] = None
    graded_at: Optional[datetime] = None
    my_review: Optional["ReviewOut"] = None
    veto_reason: Optional[str] = None
    status: str
    like_count: int
    reply_count: int
    liked_by_me: bool
    attachments: List[AttachmentOut]
    created_at: datetime
    last_activity_at: datetime
    parent_id: Optional[int]
