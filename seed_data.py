"""
Seed script to populate the database with sample data for testing.
Run with: python seed_data.py
"""
from datetime import date, timedelta
from models.database import SessionLocal, engine, Base
from models.models import Student, Attendance, Participation, Grade

# Create tables
Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    # Clear existing data
    db.query(Grade).delete()
    db.query(Participation).delete()
    db.query(Attendance).delete()
    db.query(Student).delete()
    db.commit()

    # Create sample students
    students = [
        Student(id=1, name="Alice Johnson", email="alice@school.edu"),
        Student(id=2, name="Bob Smith", email="bob@school.edu"),
        Student(id=3, name="Carol Davis", email="carol@school.edu"),
    ]
    db.add_all(students)
    db.commit()

    # Create attendance records for student 1
    today = date.today()
    attendance_records = [
        Attendance(student_id=1, date=today - timedelta(days=7), status="present"),
        Attendance(student_id=1, date=today - timedelta(days=6), status="present"),
        Attendance(student_id=1, date=today - timedelta(days=5), status="late", notes="Traffic delay"),
        Attendance(student_id=1, date=today - timedelta(days=4), status="present"),
        Attendance(student_id=1, date=today - timedelta(days=3), status="absent", notes="Sick"),
        Attendance(student_id=1, date=today - timedelta(days=2), status="excused", notes="Doctor appointment"),
        Attendance(student_id=1, date=today - timedelta(days=1), status="present"),
        Attendance(student_id=1, date=today, status="present"),
    ]
    db.add_all(attendance_records)

    # Create grades for student 1
    grades = [
        Grade(student_id=1, category="homework", score=18, max_score=20, date=today - timedelta(days=14)),
        Grade(student_id=1, category="quiz", score=8, max_score=10, date=today - timedelta(days=10)),
        Grade(student_id=1, category="homework", score=19, max_score=20, date=today - timedelta(days=7)),
        Grade(student_id=1, category="exam", score=85, max_score=100, date=today - timedelta(days=3)),
        Grade(student_id=1, category="project", score=45, max_score=50, date=today - timedelta(days=1)),
    ]
    db.add_all(grades)

    # Create participation records for student 1
    participations = [
        Participation(student_id=1, date=today - timedelta(days=5), description="Answered question about loops", points=1),
        Participation(student_id=1, date=today - timedelta(days=3), description="Led group discussion on algorithms", points=3),
        Participation(student_id=1, date=today - timedelta(days=1), description="Helped classmate debug code", points=2),
    ]
    db.add_all(participations)

    db.commit()
    print("Database seeded successfully!")
    print("\nCreated students:")
    for s in students:
        print(f"  - ID {s.id}: {s.name} ({s.email})")
    print("\nYou can now log in with student ID: 1")

except Exception as e:
    print(f"Error seeding database: {e}")
    db.rollback()
finally:
    db.close()
