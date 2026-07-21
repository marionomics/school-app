"""Seed local dev data: teacher, 3 students, one class, enrollments."""
from datetime import date

from app.database import SessionLocal
from app.models import Class, Enrollment, User
from app.services.class_codes import generate_code

db = SessionLocal()

teacher = User(
    google_id="seed-teacher", email="hola@marionomics.com", name="Mario",
    username="mario", bio="El profe.", role="teacher",
)
students = [
    User(google_id=f"seed-s{i}", email=f"alumno{i}@example.com",
         name=f"Alumno {i}", username=f"alumno{i}", bio="Estudiante de prueba.")
    for i in range(1, 4)
]
db.add_all([teacher, *students])
db.commit()

klass = Class(
    name="Microeconomía", code=generate_code(db, "MICRO"), teacher_id=teacher.id,
    start_date=date(2026, 8, 17), end_date=date(2026, 12, 4),
    schedule_json=[{"day": d, "start": "10:00", "end": "11:00"} for d in range(4)],
)
db.add(klass)
db.commit()

for s in students:
    db.add(Enrollment(user_id=s.id, class_id=klass.id))
db.commit()
print(f"Seeded. Código de clase: {klass.code}")
