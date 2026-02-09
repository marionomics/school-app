from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Date, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, date
import random
import string
from .database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    oauth_id = Column(String(255), unique=True, nullable=True)
    role = Column(String(20), nullable=False, default="student")  # student, teacher
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    attendances = relationship("Attendance", back_populates="student", cascade="all, delete-orphan")
    participations = relationship("Participation", back_populates="student", cascade="all, delete-orphan")
    grades = relationship("Grade", back_populates="student", cascade="all, delete-orphan")
    taught_classes = relationship("Class", back_populates="teacher", cascade="all, delete-orphan")
    enrollments = relationship("StudentClass", back_populates="student", cascade="all, delete-orphan")
    special_points = relationship("SpecialPoints", back_populates="student", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="student", cascade="all, delete-orphan", foreign_keys="[Submission.student_id]")


class Attendance(Base):
    __tablename__ = "attendances"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True)
    date = Column(Date, nullable=False, default=date.today)
    status = Column(String(20), nullable=False)  # present, absent, late, excused
    notes = Column(Text, nullable=True)

    # Relationships
    student = relationship("Student", back_populates="attendances")
    class_ = relationship("Class", back_populates="attendances")


class Participation(Base):
    __tablename__ = "participations"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True)
    date = Column(Date, nullable=False, default=date.today)
    description = Column(Text, nullable=False)
    points = Column(Integer, nullable=False, default=1)
    approved = Column(String(20), nullable=False, default="pending")  # pending, approved, rejected

    # Relationships
    student = relationship("Student", back_populates="participations")
    class_ = relationship("Class", back_populates="participations")


class Grade(Base):
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("grade_categories.id"), nullable=True)
    category = Column(String(50), nullable=True)  # legacy string field
    name = Column(String(200), nullable=True)  # e.g., "Reto Semana 1"
    score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False)
    date = Column(Date, nullable=False, default=date.today)

    # Relationships
    student = relationship("Student", back_populates="grades")
    class_ = relationship("Class", back_populates="grades")
    grade_category = relationship("GradeCategory")


class Class(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(20), unique=True, nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    teacher = relationship("Student", back_populates="taught_classes")
    enrollments = relationship("StudentClass", back_populates="class_", cascade="all, delete-orphan")
    attendances = relationship("Attendance", back_populates="class_")
    participations = relationship("Participation", back_populates="class_")
    grades = relationship("Grade", back_populates="class_")
    grade_categories = relationship("GradeCategory", back_populates="class_", cascade="all, delete-orphan")
    special_points = relationship("SpecialPoints", back_populates="class_", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="class_", cascade="all, delete-orphan")

    @staticmethod
    def generate_code(prefix: str = "") -> str:
        year = datetime.utcnow().year
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"{prefix.upper()}{year}{suffix}" if prefix else f"CLS{year}{suffix}"


class StudentClass(Base):
    __tablename__ = "student_classes"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    student = relationship("Student", back_populates="enrollments")
    class_ = relationship("Class", back_populates="enrollments")

    __table_args__ = (UniqueConstraint('student_id', 'class_id', name='unique_student_class'),)


class GradeCategory(Base):
    __tablename__ = "grade_categories"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    name = Column(String(100), nullable=False)  # e.g., "Retos de la Semana", "Examenes"
    weight = Column(Float, nullable=False)  # Percentage weight (e.g., 0.4 for 40%)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    class_ = relationship("Class", back_populates="grade_categories")

    __table_args__ = (UniqueConstraint('class_id', 'name', name='unique_class_category'),)


class SpecialPoints(Base):
    __tablename__ = "special_points"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    category = Column(String(20), nullable=False)  # "english" or "notebook"
    opted_in = Column(Boolean, nullable=False, default=False)
    awarded = Column(Boolean, nullable=False, default=False)
    points_value = Column(Float, nullable=False, default=0.5)  # Default 0.5 points each
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    student = relationship("Student", back_populates="special_points")
    class_ = relationship("Class", back_populates="special_points")

    __table_args__ = (UniqueConstraint('student_id', 'class_id', 'category', name='unique_student_class_special'),)


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("grade_categories.id"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(DateTime, nullable=False)
    max_points = Column(Float, nullable=False, default=100)
    allow_late = Column(Boolean, nullable=False, default=True)
    published = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    class_ = relationship("Class", back_populates="assignments")
    grade_category = relationship("GradeCategory")
    submissions = relationship("Submission", back_populates="assignment", cascade="all, delete-orphan")


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    text_content = Column(Text, nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    is_late = Column(Boolean, nullable=False, default=False)
    grade = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)
    graded_at = Column(DateTime, nullable=True)
    graded_by = Column(Integer, ForeignKey("students.id"), nullable=True)

    # Relationships
    assignment = relationship("Assignment", back_populates="submissions")
    student = relationship("Student", back_populates="submissions", foreign_keys=[student_id])

    __table_args__ = (UniqueConstraint('assignment_id', 'student_id', name='unique_assignment_student'),)
