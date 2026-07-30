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


class PostOut(BaseModel):
    id: int
    author: AuthorOut
    type: str
    class_id: Optional[int]
    class_name: Optional[str]
    content: str
    taps: Optional[int]
    status: str
    like_count: int
    reply_count: int
    liked_by_me: bool
    attachments: List[AttachmentOut]
    created_at: datetime
    last_activity_at: datetime
    parent_id: Optional[int]
