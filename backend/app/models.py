from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def session_expiry() -> datetime:
    return utcnow() + timedelta(days=30)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    google_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    username: Mapped[Optional[str]] = mapped_column(String(20), unique=True, index=True)
    bio: Mapped[str] = mapped_column(Text, default="")
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(String(20), default="student")
    grade_is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=session_expiry)

    user: Mapped[User] = relationship()


class Class(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    schedule_json: Mapped[list] = mapped_column(JSON, default=list)
    tareas_weight: Mapped[int] = mapped_column(Integer, default=30)
    examenes_weight: Mapped[int] = mapped_column(Integer, default=30)
    attendance_required_pct: Mapped[int] = mapped_column(Integer, default=80)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    teacher: Mapped[User] = relationship()


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("user_id", "class_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|ghost|polizon
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship()
    klass: Mapped[Class] = relationship()


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(20), default="regular")  # regular|participacion|tarea|examen
    class_id: Mapped[Optional[int]] = mapped_column(ForeignKey("classes.id"), index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("posts.id"), index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    taps: Mapped[Optional[int]] = mapped_column(Integer)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_entrega: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    examen_mode: Mapped[Optional[str]] = mapped_column(String(10))   # paper|digital, examen only
    graded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    veto_reason: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|deleted|vetoed
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    edited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    author: Mapped[User] = relationship()
    klass: Mapped[Optional[Class]] = relationship()
    attachments: Mapped[List["Attachment"]] = relationship(back_populates="post")


class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (UniqueConstraint("user_id", "post_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    file_key: Mapped[str] = mapped_column(String(500))
    file_name: Mapped[str] = mapped_column(String(255))
    file_size: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    post: Mapped[Post] = relationship(back_populates="attachments")


class PointsConfig(Base):
    __tablename__ = "points_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), unique=True, index=True)
    tap_value: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("1.0"))
    like_value: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("1.0"))
    like_exponent: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.5"))
    like_cap: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    daily_post_limit: Mapped[int] = mapped_column(Integer, default=5)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("item_post_id", "student_id",
                                       name="uq_review_item_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # The tarea or examen being graded — NOT the entrega.
    item_post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Which submission this score was written against. NULL for a paper examen.
    entrega_post_id: Mapped[Optional[int]] = mapped_column(ForeignKey("posts.id"))
    reviewer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    # Scale follows the item type: 0–100 for a tarea, 1–10 for an examen.
    score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    auto_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class ClassSession(Base):
    __tablename__ = "class_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), index=True)
    # Annotation is a string forward-ref on purpose: the attribute name "date"
    # would otherwise shadow the `date` type imported at module scope when
    # SQLAlchemy evaluates `Mapped[date]` eagerly, resolving to the
    # MappedColumn instance instead of datetime.date.
    date: Mapped["date"] = mapped_column(Date)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("class_sessions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20))  # present|absent|late|excused
    justification_text: Mapped[Optional[str]] = mapped_column(Text)
    justification_file_key: Mapped[Optional[str]] = mapped_column(String(500))
    justification_status: Mapped[Optional[str]] = mapped_column(String(20))  # pending|approved|rejected
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class PointsLedger(Base):
    __tablename__ = "points_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    class_id: Mapped[Optional[int]] = mapped_column(ForeignKey("classes.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(30))  # participacion|forum_like|incentive|penalty|bonus|adjustment
    source_id: Mapped[int] = mapped_column(Integer)  # NO FK on purpose: polymorphic; likes get hard-deleted
    points: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
