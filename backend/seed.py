"""Seed local dev data: teacher, 3 students, one class, posts, sessions."""
from datetime import date, datetime, timezone

from app.database import SessionLocal
from app.models import (AttendanceRecord, Class, ClassSession, Enrollment,
                        PointsLedger, Post, User, utcnow)
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

# Tarea
tarea = Post(
    author_id=teacher.id, type="tarea", class_id=klass.id,
    content="Leer capítulo 3 de Pindyck y responder: ¿qué es la elasticidad precio?",
    due_date=datetime(2026, 8, 24, 23, 59, 0, tzinfo=timezone.utc),
)
db.add(tarea)
db.commit()

# Entregas de los primeros dos alumnos
for s in students[:2]:
    entrega = Post(
        author_id=s.id, type="regular", class_id=klass.id,
        parent_id=tarea.id, is_entrega=True,
        content=f"Mi respuesta de {s.name}: La elasticidad precio mide cuánto varía la cantidad demandada ante un cambio en el precio.",
        created_at=datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc),
    )
    db.add(entrega)
db.commit()

# Examen
examen = Post(
    author_id=teacher.id, type="examen", class_id=klass.id,
    content="Parcial 1 — Oferta, demanda y elasticidad",
    examen_mode="paper",
)
db.add(examen)
db.commit()

# Participaciones con puntos en el ledger
for i, s in enumerate(students):
    taps = (i % 3) + 1
    part = Post(
        author_id=s.id, type="participacion", class_id=klass.id,
        content=f"Participación de {s.name}: Explicó el concepto de costo de oportunidad con un ejemplo.",
        taps=taps,
    )
    db.add(part)
    db.commit()
    db.add(PointsLedger(
        user_id=s.id, class_id=klass.id,
        source_type="participacion", source_id=part.id,
        points=taps,
    ))
db.commit()

# Sesión abierta con asistencia
session = ClassSession(
    class_id=klass.id, date=date.today(), opened_at=utcnow(),
)
db.add(session)
db.commit()

attendance_statuses = ["present", "present", "absent"]
for s, status in zip(students, attendance_statuses):
    db.add(AttendanceRecord(session_id=session.id, user_id=s.id, status=status))
db.commit()

print(f"Seeded. Código de clase: {klass.code}")
print(f"  Teacher: {teacher.email}")
print(f"  Students: {[s.username for s in students]}")
print(f"  Session ID: {session.id} (open, today)")
