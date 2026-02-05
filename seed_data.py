"""
Seed script to populate the database with sample data for testing.
Run with: python seed_data.py
"""
import os
from datetime import date, timedelta
from dotenv import load_dotenv
from models.database import SessionLocal, engine, Base
from models.models import Student, Attendance, Participation, Grade, Class, StudentClass

load_dotenv()

# Create tables
Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    # Clear existing data (order matters due to foreign keys)
    db.query(Grade).delete()
    db.query(Participation).delete()
    db.query(Attendance).delete()
    db.query(StudentClass).delete()
    db.query(Class).delete()
    db.query(Student).delete()
    db.commit()

    # Create teacher account if TEACHER_EMAIL is set
    teacher_email = os.getenv("TEACHER_EMAIL")
    teacher = None
    if teacher_email:
        teacher = Student(name="Teacher", email=teacher_email, role="teacher")
        db.add(teacher)
        db.commit()
        db.refresh(teacher)

    # Create sample students
    alice = Student(name="Alice Johnson", email="alice@school.edu", role="student")
    bob = Student(name="Bob Smith", email="bob@school.edu", role="student")
    carol = Student(name="Carol Davis", email="carol@school.edu", role="student")
    students = [alice, bob, carol]
    db.add_all(students)
    db.commit()

    # Refresh to get IDs
    for s in students:
        db.refresh(s)

    # Create sample class if teacher exists
    sample_class = None
    if teacher:
        sample_class = Class(
            name="Microeconomia 2026",
            code=Class.generate_code("MICRO"),
            teacher_id=teacher.id,
        )
        db.add(sample_class)
        db.commit()
        db.refresh(sample_class)

        # Enroll all students in the class
        for student in students:
            enrollment = StudentClass(student_id=student.id, class_id=sample_class.id)
            db.add(enrollment)
        db.commit()

    # Create attendance records for Alice (with class_id if class exists)
    today = date.today()
    attendance_records = [
        Attendance(student_id=alice.id, class_id=sample_class.id if sample_class else None, date=today - timedelta(days=7), status="present"),
        Attendance(student_id=alice.id, class_id=sample_class.id if sample_class else None, date=today - timedelta(days=6), status="present"),
        Attendance(student_id=alice.id, class_id=sample_class.id if sample_class else None, date=today - timedelta(days=5), status="late", notes="Traffic delay"),
        Attendance(student_id=alice.id, class_id=sample_class.id if sample_class else None, date=today - timedelta(days=4), status="present"),
        Attendance(student_id=alice.id, class_id=sample_class.id if sample_class else None, date=today - timedelta(days=3), status="absent", notes="Sick"),
        Attendance(student_id=alice.id, class_id=sample_class.id if sample_class else None, date=today - timedelta(days=2), status="excused", notes="Doctor appointment"),
        Attendance(student_id=alice.id, class_id=sample_class.id if sample_class else None, date=today - timedelta(days=1), status="present"),
        Attendance(student_id=alice.id, class_id=sample_class.id if sample_class else None, date=today, status="present"),
    ]
    db.add_all(attendance_records)

    # Create grades for Alice (with class_id if class exists)
    grades = [
        Grade(student_id=alice.id, class_id=sample_class.id if sample_class else None, category="homework", score=18, max_score=20, date=today - timedelta(days=14)),
        Grade(student_id=alice.id, class_id=sample_class.id if sample_class else None, category="quiz", score=8, max_score=10, date=today - timedelta(days=10)),
        Grade(student_id=alice.id, class_id=sample_class.id if sample_class else None, category="homework", score=19, max_score=20, date=today - timedelta(days=7)),
        Grade(student_id=alice.id, class_id=sample_class.id if sample_class else None, category="exam", score=85, max_score=100, date=today - timedelta(days=3)),
        Grade(student_id=alice.id, class_id=sample_class.id if sample_class else None, category="project", score=45, max_score=50, date=today - timedelta(days=1)),
    ]
    db.add_all(grades)

    # Create participation records for Alice (with class_id if class exists)
    participations = [
        Participation(student_id=alice.id, class_id=sample_class.id if sample_class else None, date=today - timedelta(days=5), description="Answered question about loops", points=1, approved="approved"),
        Participation(student_id=alice.id, class_id=sample_class.id if sample_class else None, date=today - timedelta(days=3), description="Led group discussion on algorithms", points=3, approved="approved"),
        Participation(student_id=alice.id, class_id=sample_class.id if sample_class else None, date=today - timedelta(days=1), description="Helped classmate debug code", points=2, approved="pending"),
    ]
    db.add_all(participations)

    db.commit()
    print("Database seeded successfully!")
    if teacher:
        print(f"\nTeacher account: {teacher.email}")
    else:
        print("\nNo teacher account created (set TEACHER_EMAIL in .env)")

    if sample_class:
        print(f"\nSample class created:")
        print(f"  Name: {sample_class.name}")
        print(f"  Code: {sample_class.code}")
        print(f"  Students enrolled: {len(students)}")
    else:
        print("\nNo sample class created (requires teacher account)")

    print("\nCreated students:")
    for s in students:
        print(f"  - {s.name} ({s.email})")
    print("\nLogin with Google OAuth using your configured account.")

except Exception as e:
    print(f"Error seeding database: {e}")
    db.rollback()
finally:
    db.close()
