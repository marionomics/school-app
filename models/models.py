from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Date
from sqlalchemy.orm import relationship
from datetime import datetime, date
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


class Attendance(Base):
    __tablename__ = "attendances"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    date = Column(Date, nullable=False, default=date.today)
    status = Column(String(20), nullable=False)  # present, absent, late, excused
    notes = Column(Text, nullable=True)

    # Relationships
    student = relationship("Student", back_populates="attendances")


class Participation(Base):
    __tablename__ = "participations"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    date = Column(Date, nullable=False, default=date.today)
    description = Column(Text, nullable=False)
    points = Column(Integer, nullable=False, default=1)
    approved = Column(String(20), nullable=False, default="pending")  # pending, approved, rejected

    # Relationships
    student = relationship("Student", back_populates="participations")


class Grade(Base):
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    category = Column(String(50), nullable=False)  # homework, quiz, exam, project
    score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False)
    date = Column(Date, nullable=False, default=date.today)

    # Relationships
    student = relationship("Student", back_populates="grades")
