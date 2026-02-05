from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Date, UniqueConstraint
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
    category = Column(String(50), nullable=False)  # homework, quiz, exam, project
    score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False)
    date = Column(Date, nullable=False, default=date.today)

    # Relationships
    student = relationship("Student", back_populates="grades")
    class_ = relationship("Class", back_populates="grades")


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
