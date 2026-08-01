# Phase 3 — Listo para clases: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Attendance tracking with a session lifecycle, a teacher-facing grade roster, a per-student grade breakdown for teachers, a class panel page with Roster/Calificaciones tabs, and a full-screen "Pasar lista" attendance UI. The grade engine already accounts for `absent` records; this phase wires real sessions and records into it for the first time.

**Architecture:** No new migrations are needed — `class_sessions` and `attendance_records` tables already exist. All new backend work is a new router file `attendance.py` registered in `main.py`, plus a second `class_grades_router` in `grades.py`. The frontend gets one new page (`ClassPanel`) at `/clases/:id` and one new page (`PasarLista`) at `/pasar-lista/:class_id/:session_id`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 typed `Mapped[]` columns, Alembic, pytest; React + Vite + TanStack Query + Tailwind + shadcn. SQLite locally, PostgreSQL in CI. No venv — tests run with `python3 -m pytest` from `backend/`.

## Global Constraints

- `late` status = present for grade purposes. Only `absent` with no approved justification counts as a falta.
- Ghost and polizon enrollments appear in the Roster tab with their icon.
- The upsert for `PUT /api/sessions/{session_id}/attendance` is: delete all existing `AttendanceRecord` rows for the session, then insert the new list. Safe because no justification workflows exist yet.
- Never resurect v1 schema.
- All user-facing copy lives in `frontend/src/strings/es.ts`.
- Every commit must leave `main` deployable.
- Run backend tests with `python3 -m pytest` from `backend/`.

---

### Task 1: Attendance router — session lifecycle endpoints

**Files:**
- Create: `backend/app/routers/attendance.py`
- Modify: `backend/app/main.py`, `backend/app/schemas.py`

**Interfaces:**
- Produces:
  - `POST /api/classes/{class_id}/sessions` → `SessionOut` (201)
  - `DELETE /api/classes/{class_id}/sessions/{session_id}` → 204
  - `GET /api/classes/{class_id}/sessions` → `{"sessions": [SessionOut]}`
  - `GET /api/classes/{class_id}/sessions/active` → `SessionOut | null`

- [ ] **Step 1: Add `SessionOut` schema to `backend/app/schemas.py`**

After `ClassSettingsOut`:

```python
class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    class_id: int
    date: date
    opened_at: Optional[datetime]
    closed_at: Optional[datetime]
    attendance_count: int = 0
```

- [ ] **Step 2: Create `backend/app/routers/attendance.py`**

```python
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_teacher
from app.database import get_db
from app.models import AttendanceRecord, Class, ClassSession, User, utcnow
from app.schemas import SessionOut

router = APIRouter(tags=["attendance"])


def _owned_class(db: Session, class_id: int, teacher: User) -> Class:
    klass = db.get(Class, class_id)
    if klass is None:
        raise HTTPException(status_code=404, detail="Clase no encontrada")
    if klass.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="No eres profesor de esa clase")
    return klass


def _owned_session(db: Session, class_id: int, session_id: int,
                   teacher: User) -> ClassSession:
    _owned_class(db, class_id, teacher)
    session = db.get(ClassSession, session_id)
    if session is None or session.class_id != class_id:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return session


def _attendance_count(db: Session, session_id: int) -> int:
    return (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.session_id == session_id)
        .count()
    )


def _to_out(db: Session, s: ClassSession) -> SessionOut:
    return SessionOut(
        id=s.id,
        class_id=s.class_id,
        date=s.date,
        opened_at=s.opened_at,
        closed_at=s.closed_at,
        attendance_count=_attendance_count(db, s.id),
    )


@router.post("/api/classes/{class_id}/sessions", status_code=201,
             response_model=SessionOut)
def open_session(
    class_id: int,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    _owned_class(db, class_id, teacher)
    today = date_type.today()
    existing = (
        db.query(ClassSession)
        .filter(ClassSession.class_id == class_id,
                ClassSession.date == today,
                ClassSession.closed_at.is_(None))
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=409,
                            detail="Ya hay una sesión abierta para hoy")
    session = ClassSession(class_id=class_id, date=today, opened_at=utcnow())
    db.add(session)
    db.commit()
    db.refresh(session)
    return _to_out(db, session)


@router.delete("/api/classes/{class_id}/sessions/{session_id}", status_code=204)
def close_session(
    class_id: int,
    session_id: int,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    session = _owned_session(db, class_id, session_id, teacher)
    session.closed_at = utcnow()
    db.commit()


@router.get("/api/classes/{class_id}/sessions/active")
def active_session(
    class_id: int,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    _owned_class(db, class_id, teacher)
    session = (
        db.query(ClassSession)
        .filter(ClassSession.class_id == class_id,
                ClassSession.closed_at.is_(None))
        .order_by(ClassSession.opened_at.desc())
        .first()
    )
    if session is None:
        return None
    return _to_out(db, session)


@router.get("/api/classes/{class_id}/sessions")
def list_sessions(
    class_id: int,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    _owned_class(db, class_id, teacher)
    sessions = (
        db.query(ClassSession)
        .filter(ClassSession.class_id == class_id)
        .order_by(ClassSession.date.desc(), ClassSession.opened_at.desc())
        .all()
    )
    return {"sessions": [_to_out(db, s) for s in sessions]}
```

Note: `active_session` is registered BEFORE `list_sessions/{session_id}` (no such route exists here, but ordering is intentional for safety).

- [ ] **Step 3: Add attendance records schemas and endpoint**

In `backend/app/schemas.py` add:

```python
class AttendanceRecordIn(BaseModel):
    user_id: int
    status: str  # present|absent|late

class AttendancePut(BaseModel):
    records: list[AttendanceRecordIn]
```

In `backend/app/routers/attendance.py` add the put endpoint:

```python
from app.schemas import AttendancePut, AttendanceRecordIn, SessionOut

@router.put("/api/sessions/{session_id}/attendance")
def put_attendance(
    session_id: int,
    body: AttendancePut,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    session = db.get(ClassSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    _owned_class(db, session.class_id, teacher)

    db.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == session_id
    ).delete()

    for rec in body.records:
        db.add(AttendanceRecord(
            session_id=session_id,
            user_id=rec.user_id,
            status=rec.status,
        ))
    db.commit()
    return {"saved": len(body.records)}
```

- [ ] **Step 4: Register in `backend/app/main.py`**

```python
from app.routers import attendance as attendance_router
# ...
app.include_router(attendance_router.router)
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/attendance.py backend/app/main.py backend/app/schemas.py
git commit -m "feat(attendance): session lifecycle + attendance records endpoints"
```

---

### Task 2: Attendance tests

**Files:**
- Create: `backend/tests/test_attendance.py`

- [ ] **Step 1: Create `backend/tests/test_attendance.py`**

```python
from datetime import date

from app.models import AttendanceRecord, ClassSession, utcnow


def _open(client, headers, klass_id):
    return client.post(f"/api/classes/{klass_id}/sessions", headers=headers)


def _close(client, headers, klass_id, session_id):
    return client.delete(
        f"/api/classes/{klass_id}/sessions/{session_id}", headers=headers
    )


def _put(client, headers, session_id, records):
    return client.put(
        f"/api/sessions/{session_id}/attendance",
        json={"records": records},
        headers=headers,
    )


def test_teacher_opens_session(client, teacher_headers, klass):
    r = _open(client, teacher_headers, klass.id)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["class_id"] == klass.id
    assert body["closed_at"] is None
    assert body["opened_at"] is not None


def test_student_cannot_open_session(client, auth_headers, klass):
    r = _open(client, auth_headers, klass.id)
    assert r.status_code == 403


def test_duplicate_open_session_rejected(client, teacher_headers, klass):
    _open(client, teacher_headers, klass.id)
    r = _open(client, teacher_headers, klass.id)
    assert r.status_code == 409


def test_close_session(client, teacher_headers, klass):
    session_id = _open(client, teacher_headers, klass.id).json()["id"]
    r = _close(client, teacher_headers, klass.id, session_id)
    assert r.status_code == 204


def test_list_sessions_most_recent_first(client, db, teacher_headers, klass):
    s1 = ClassSession(class_id=klass.id, date=date(2026, 8, 17), opened_at=utcnow())
    s2 = ClassSession(class_id=klass.id, date=date(2026, 8, 18), opened_at=utcnow())
    db.add_all([s1, s2])
    db.commit()
    r = client.get(f"/api/classes/{klass.id}/sessions", headers=teacher_headers)
    assert r.status_code == 200
    dates = [s["date"] for s in r.json()["sessions"]]
    assert dates == sorted(dates, reverse=True)


def test_active_session_returns_open_session(client, teacher_headers, klass):
    session_id = _open(client, teacher_headers, klass.id).json()["id"]
    r = client.get(f"/api/classes/{klass.id}/sessions/active",
                   headers=teacher_headers)
    assert r.status_code == 200
    assert r.json()["id"] == session_id


def test_active_session_returns_null_when_closed(client, teacher_headers, klass):
    session_id = _open(client, teacher_headers, klass.id).json()["id"]
    _close(client, teacher_headers, klass.id, session_id)
    r = client.get(f"/api/classes/{klass.id}/sessions/active",
                   headers=teacher_headers)
    assert r.status_code == 200
    assert r.json() is None


def test_attendance_count_in_session_list(client, teacher_headers,
                                           klass, student, enrolled):
    session_id = _open(client, teacher_headers, klass.id).json()["id"]
    _put(client, teacher_headers, session_id,
         [{"user_id": student.id, "status": "absent"}])
    r = client.get(f"/api/classes/{klass.id}/sessions", headers=teacher_headers)
    session = next(s for s in r.json()["sessions"] if s["id"] == session_id)
    assert session["attendance_count"] == 1


def test_put_attendance_saves_records(client, teacher_headers, klass, student, enrolled):
    session_id = _open(client, teacher_headers, klass.id).json()["id"]
    r = _put(client, teacher_headers, session_id,
             [{"user_id": student.id, "status": "present"}])
    assert r.status_code == 200
    assert r.json()["saved"] == 1


def test_put_attendance_upserts_replaces_previous(client, db, teacher_headers,
                                                   klass, student, enrolled):
    session_id = _open(client, teacher_headers, klass.id).json()["id"]
    _put(client, teacher_headers, session_id,
         [{"user_id": student.id, "status": "present"}])
    _put(client, teacher_headers, session_id,
         [{"user_id": student.id, "status": "absent"}])
    records = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.session_id == session_id)
        .all()
    )
    assert len(records) == 1
    assert records[0].status == "absent"


def test_absent_record_appears_in_grade(client, teacher_headers,
                                         auth_headers, klass, student, enrolled):
    session_id = _open(client, teacher_headers, klass.id).json()["id"]
    _put(client, teacher_headers, session_id,
         [{"user_id": student.id, "status": "absent"}])
    grade = client.get(
        f"/api/students/me/grade?class_id={klass.id}", headers=auth_headers
    ).json()
    assert grade["faltas"]["count"] == 1
    assert grade["faltas"]["points"] == 10.0
    assert grade["total"] == -10.0


def test_late_does_not_count_as_falta(client, teacher_headers,
                                       auth_headers, klass, student, enrolled):
    session_id = _open(client, teacher_headers, klass.id).json()["id"]
    _put(client, teacher_headers, session_id,
         [{"user_id": student.id, "status": "late"}])
    grade = client.get(
        f"/api/students/me/grade?class_id={klass.id}", headers=auth_headers
    ).json()
    assert grade["faltas"]["count"] == 0
```

- [ ] **Step 2: Run**

```bash
cd /Users/marius/Proyectos/coding/school-app/backend && python3 -m pytest tests/test_attendance.py -v
```

Expected: 12 tests green.

- [ ] **Step 3: Full suite**

```bash
python3 -m pytest -q
```

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_attendance.py
git commit -m "test(attendance): session lifecycle and attendance records tests"
```

---

### Task 3: Roster and teacher grade endpoints

**Files:**
- Modify: `backend/app/routers/grades.py`, `backend/app/schemas.py`, `backend/app/main.py`

**Interfaces:**
- Produces:
  - `GET /api/classes/{class_id}/roster` → `{"students": [RosterStudent]}`
  - `GET /api/classes/{class_id}/students/{student_id}/grade` → `GradeBreakdown` shape

- [ ] **Step 1: Add `RosterStudent` to `backend/app/schemas.py`**

```python
class RosterStudent(BaseModel):
    id: int
    name: str
    username: Optional[str]
    avatar_url: Optional[str]
    status: str  # active|ghost|polizon
    grade: float
    faltas: int
```

- [ ] **Step 2: Check what's already imported in `backend/app/routers/grades.py`**

Read the file to understand what's there before modifying.

- [ ] **Step 3: Add `class_grades_router` to `backend/app/routers/grades.py`**

Add after all existing imports (add any missing ones: `get_current_teacher`, `RosterStudent`, `faltas_breakdown`, `Enrollment`, `round_grade`):

```python
from app.auth.deps import get_current_teacher
from app.schemas import RosterStudent
from app.services.grades import faltas_breakdown

class_grades_router = APIRouter(tags=["grades"])


def _teacher_owned_class(db: Session, class_id: int, teacher: User) -> Class:
    klass = db.get(Class, class_id)
    if klass is None:
        raise HTTPException(status_code=404, detail="Clase no encontrada")
    if klass.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="No eres profesor de esa clase")
    return klass


@class_grades_router.get("/api/classes/{class_id}/roster")
def class_roster(
    class_id: int,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    klass = _teacher_owned_class(db, class_id, teacher)
    enrollments = (
        db.query(Enrollment)
        .filter(Enrollment.class_id == class_id)
        .all()
    )
    now = utcnow()
    students = []
    for e in enrollments:
        g = calculate_grade(db, e.user_id, klass, now=now)
        faltas_count, _ = faltas_breakdown(db, e.user_id, class_id)
        students.append(RosterStudent(
            id=e.user.id,
            name=e.user.name,
            username=e.user.username,
            avatar_url=e.user.avatar_url,
            status=e.status,
            grade=float(round_grade(g.total)),
            faltas=faltas_count,
        ))
    return {"students": students}


@class_grades_router.get("/api/classes/{class_id}/students/{student_id}/grade")
def student_grade_for_teacher(
    class_id: int,
    student_id: int,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    klass = _teacher_owned_class(db, class_id, teacher)
    enrollment = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == student_id,
                Enrollment.class_id == class_id)
        .first()
    )
    if enrollment is None:
        raise HTTPException(status_code=404,
                            detail="Ese alumno no está en esta clase")
    return _summary(db, student_id, klass)
```

- [ ] **Step 4: Register in `backend/app/main.py`**

```python
from app.routers.grades import class_grades_router
# ...
app.include_router(class_grades_router)
```

- [ ] **Step 5: Run full suite**

```bash
cd /Users/marius/Proyectos/coding/school-app/backend && python3 -m pytest -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/grades.py backend/app/schemas.py backend/app/main.py
git commit -m "feat(grades): roster and teacher-facing student grade endpoints"
```

---

### Task 4: Roster and teacher grade tests

**Files:**
- Create: `backend/tests/test_roster.py`

- [ ] **Step 1: Add `ghost` fixture to `backend/tests/conftest.py`**

Check if a `ghost` fixture exists; if not, add:

```python
@pytest.fixture()
def ghost(db, klass):
    from app.models import Enrollment, User
    u = User(google_id="seed-ghost", email="ghost@example.com",
             name="Ghost Student", role="student")
    db.add(u)
    db.flush()
    db.add(Enrollment(user_id=u.id, class_id=klass.id, status="ghost"))
    db.commit()
    return u
```

- [ ] **Step 2: Create `backend/tests/test_roster.py`**

```python
from decimal import Decimal

from app.models import AttendanceRecord, ClassSession, PointsLedger, utcnow


def test_roster_requires_teacher(client, auth_headers, klass):
    r = client.get(f"/api/classes/{klass.id}/roster", headers=auth_headers)
    assert r.status_code == 403


def test_roster_returns_all_enrollments(client, teacher_headers, klass,
                                         student, enrolled, ghost):
    r = client.get(f"/api/classes/{klass.id}/roster", headers=teacher_headers)
    assert r.status_code == 200, r.text
    ids = {s["id"] for s in r.json()["students"]}
    assert student.id in ids
    assert ghost.id in ids


def test_roster_shows_ghost_status(client, teacher_headers, klass, ghost):
    r = client.get(f"/api/classes/{klass.id}/roster", headers=teacher_headers)
    row = next(s for s in r.json()["students"] if s["id"] == ghost.id)
    assert row["status"] == "ghost"


def test_roster_grade_reflects_falta(client, db, teacher_headers, klass,
                                       student, enrolled):
    session = ClassSession(class_id=klass.id, date=utcnow().date(),
                           opened_at=utcnow())
    db.add(session)
    db.flush()
    db.add(AttendanceRecord(session_id=session.id, user_id=student.id,
                            status="absent"))
    db.commit()
    r = client.get(f"/api/classes/{klass.id}/roster", headers=teacher_headers)
    row = next(s for s in r.json()["students"] if s["id"] == student.id)
    assert row["faltas"] == 1
    assert row["grade"] == -10.0


def test_roster_grade_reflects_points(client, db, teacher_headers, klass,
                                        student, enrolled):
    db.add(PointsLedger(user_id=student.id, class_id=klass.id,
                        source_type="participacion", source_id=1,
                        points=Decimal("5.00")))
    db.commit()
    r = client.get(f"/api/classes/{klass.id}/roster", headers=teacher_headers)
    row = next(s for s in r.json()["students"] if s["id"] == student.id)
    assert row["grade"] == 5.0


def test_teacher_can_view_student_grade(client, teacher_headers, klass,
                                         student, enrolled):
    r = client.get(
        f"/api/classes/{klass.id}/students/{student.id}/grade",
        headers=teacher_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["class_id"] == klass.id
    assert "total" in body
    assert "faltas" in body


def test_teacher_grade_view_requires_teacher(client, auth_headers, klass,
                                               student, enrolled):
    r = client.get(
        f"/api/classes/{klass.id}/students/{student.id}/grade",
        headers=auth_headers,
    )
    assert r.status_code == 403


def test_teacher_grade_view_404_if_not_enrolled(client, teacher_headers,
                                                  klass, student):
    r = client.get(
        f"/api/classes/{klass.id}/students/{student.id}/grade",
        headers=teacher_headers,
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Run**

```bash
cd /Users/marius/Proyectos/coding/school-app/backend && python3 -m pytest tests/test_roster.py -v
```

- [ ] **Step 3: Full suite**

```bash
python3 -m pytest -q
```

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_roster.py backend/tests/conftest.py
git commit -m "test(grades): roster and teacher-facing student grade tests"
```

---

### Task 5: Frontend types and strings

**Files:**
- Modify: `frontend/src/lib/types.ts`, `frontend/src/strings/es.ts`

- [ ] **Step 1: Append to `frontend/src/lib/types.ts`**

```ts
export interface SessionOut {
  id: number;
  class_id: number;
  date: string;
  opened_at: string | null;
  closed_at: string | null;
  attendance_count: number;
}

export interface RosterStudent {
  id: number;
  name: string;
  username: string | null;
  avatar_url: string | null;
  status: "active" | "ghost" | "polizon";
  grade: number;
  faltas: number;
}

export type StudentGradeView = GradeSummary;

export interface MemberOut {
  id: number;
  name: string;
  username: string | null;
  avatar_url: string | null;
  status: "active" | "ghost" | "polizon";
}

export interface ClassDetailWithMembers extends ClassOut {
  members: MemberOut[];
}
```

- [ ] **Step 2: Add strings to `frontend/src/strings/es.ts`** (inside `es`, after `configurar`):

```ts
  panel: {
    tabRoster: "Lista",
    tabCalificaciones: "Calificaciones",
    rosterEmpty: "Sin alumnos inscritos.",
    grade: "Calificación",
    faltas: "Faltas",
    statusGhost: "👻",
    statusPolizon: "🥷",
    loadingRoster: "Cargando lista…",
    loadingCalif: "Cargando calificaciones…",
    errorRoster: "No se pudo cargar la lista",
    errorCalif: "No se pudo cargar las calificaciones",
    openSession: "Abrir sesión",
    sessionOpen: "Sesión abierta",
    closeSession: "Cerrar sesión",
    noActiveSession: "Sin sesión abierta hoy",
    openSessionError: "No se pudo abrir la sesión",
    closeSessionError: "No se pudo cerrar la sesión",
    tomarLista: "Tomar lista",
  },
  asistencia: {
    title: "Pasar lista",
    saveButton: "Guardar",
    saving: "Guardando…",
    saved: "Lista guardada",
    saveError: "No se pudo guardar la lista",
    statusPresent: "P",
    statusAbsent: "F",
    statusLate: "T",
    emptyStudents: "Sin alumnos inscritos.",
    back: "Volver",
  },
```

- [ ] **Step 3: TypeScript check**

```bash
cd /Users/marius/Proyectos/coding/school-app/frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/strings/es.ts
git commit -m "feat(frontend): SessionOut, RosterStudent, panel/asistencia strings"
```

---

### Task 6: Class panel page (`/clases/:id`)

**Files:**
- Create: `frontend/src/pages/ClassPanel.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/pages/Classes.tsx`

- [ ] **Step 1: Create `frontend/src/pages/ClassPanel.tsx`**

```tsx
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/Toaster";
import { es } from "@/strings/es";
import type {
  ClassDetailWithMembers,
  RosterStudent,
  SessionOut,
  StudentGradeView,
} from "@/lib/types";

type Tab = "roster" | "calificaciones";

export default function ClassPanel() {
  const { id } = useParams<{ id: string }>();
  const classId = Number(id);
  const { user } = useAuth();
  const isTeacher = user?.role === "teacher";
  const [tab, setTab] = useState<Tab>("roster");
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null);
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();

  const detail = useQuery({
    queryKey: ["class-detail", classId],
    queryFn: () => api<ClassDetailWithMembers>(`/api/classes/${classId}`),
    enabled: !isNaN(classId),
  });

  const activeSession = useQuery({
    queryKey: ["session-active", classId],
    queryFn: () =>
      api<SessionOut | null>(`/api/classes/${classId}/sessions/active`),
    enabled: isTeacher && !isNaN(classId),
  });

  const roster = useQuery({
    queryKey: ["roster", classId],
    queryFn: () =>
      api<{ students: RosterStudent[] }>(`/api/classes/${classId}/roster`),
    enabled: isTeacher && tab === "calificaciones" && !isNaN(classId),
    select: (d) => d.students,
  });

  const studentGrade = useQuery({
    queryKey: ["student-grade", classId, selectedStudentId],
    queryFn: () =>
      api<StudentGradeView>(
        `/api/classes/${classId}/students/${selectedStudentId}/grade`,
      ),
    enabled: selectedStudentId !== null,
  });

  const openSession = useMutation({
    mutationFn: () =>
      api<SessionOut>(`/api/classes/${classId}/sessions`, { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["session-active", classId] });
    },
    onError: () => toast.show(es.panel.openSessionError),
  });

  const closeSession = useMutation({
    mutationFn: (sessionId: number) =>
      api<void>(`/api/classes/${classId}/sessions/${sessionId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["session-active", classId] });
    },
    onError: () => toast.show(es.panel.closeSessionError),
  });

  const klass = detail.data;
  const session = activeSession.data ?? null;

  return (
    <div className="mx-auto flex max-w-md flex-col gap-4 p-4">
      <button
        onClick={() => navigate("/clases")}
        className="self-start text-sm text-primary underline"
      >
        ← {es.asistencia.back}
      </button>

      <h1 className="text-xl font-bold">
        {klass?.name ?? es.common.loading}
      </h1>

      {isTeacher && (
        <div className="flex items-center justify-between rounded-lg border p-3 text-sm">
          <span>
            {session ? es.panel.sessionOpen : es.panel.noActiveSession}
          </span>
          {session ? (
            <div className="flex gap-2">
              <button
                onClick={() =>
                  navigate(`/pasar-lista/${classId}/${session.id}`)
                }
                className="rounded-md bg-primary px-3 py-1 text-xs text-primary-foreground"
              >
                {es.panel.tomarLista}
              </button>
              <button
                onClick={() => closeSession.mutate(session.id)}
                disabled={closeSession.isPending}
                className="rounded-md border px-3 py-1 text-xs"
              >
                {es.panel.closeSession}
              </button>
            </div>
          ) : (
            <button
              onClick={() => openSession.mutate()}
              disabled={openSession.isPending}
              className="rounded-md bg-primary px-3 py-1 text-xs text-primary-foreground"
            >
              {es.panel.openSession}
            </button>
          )}
        </div>
      )}

      {isTeacher && (
        <div className="flex gap-2">
          {(["roster", "calificaciones"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-full px-3 py-1 text-sm ${
                tab === t ? "bg-primary text-primary-foreground" : "border"
              }`}
            >
              {t === "roster" ? es.panel.tabRoster : es.panel.tabCalificaciones}
            </button>
          ))}
        </div>
      )}

      {tab === "roster" && (
        <ul className="divide-y rounded-lg border">
          {detail.isPending && (
            <li className="px-4 py-3 text-sm text-muted-foreground">
              {es.panel.loadingRoster}
            </li>
          )}
          {detail.isError && (
            <li className="px-4 py-3 text-sm text-destructive">
              {es.panel.errorRoster}
            </li>
          )}
          {!detail.isPending &&
            (detail.data?.members ?? []).length === 0 && (
              <li className="px-4 py-3 text-sm text-muted-foreground">
                {es.panel.rosterEmpty}
              </li>
            )}
          {(detail.data?.members ?? []).map((m) => (
            <li key={m.id} className="flex items-center gap-3 px-4 py-3">
              <span>
                {m.status === "ghost"
                  ? es.panel.statusGhost
                  : m.status === "polizon"
                    ? es.panel.statusPolizon
                    : ""}
              </span>
              <span className="font-medium">{m.name}</span>
              {m.username && (
                <span className="text-sm text-muted-foreground">
                  @{m.username}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {tab === "calificaciones" && isTeacher && (
        <ul className="divide-y rounded-lg border">
          {roster.isPending && (
            <li className="px-4 py-3 text-sm text-muted-foreground">
              {es.panel.loadingCalif}
            </li>
          )}
          {roster.isError && (
            <li className="px-4 py-3 text-sm text-destructive">
              {es.panel.errorCalif}
            </li>
          )}
          {(roster.data ?? []).map((s) => (
            <li
              key={s.id}
              onClick={() => setSelectedStudentId(s.id)}
              className="flex cursor-pointer items-center justify-between px-4 py-3 hover:bg-accent"
            >
              <div className="flex items-center gap-2">
                <span>
                  {s.status === "ghost"
                    ? es.panel.statusGhost
                    : s.status === "polizon"
                      ? es.panel.statusPolizon
                      : ""}
                </span>
                <span className="font-medium">{s.name}</span>
              </div>
              <div className="flex flex-col items-end text-sm">
                <span className="font-semibold text-primary">
                  {s.grade} {es.grade.points}
                </span>
                {s.faltas > 0 && (
                  <span className="text-xs text-destructive">
                    {s.faltas} {es.panel.faltas}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {selectedStudentId !== null && (
        <div
          className="fixed inset-0 z-40 flex items-end bg-black/40"
          onClick={() => setSelectedStudentId(null)}
        >
          <div
            className="max-h-[80dvh] w-full overflow-y-auto rounded-t-2xl bg-background p-5"
            onClick={(e) => e.stopPropagation()}
          >
            {studentGrade.isPending && (
              <p className="text-muted-foreground">{es.common.loading}</p>
            )}
            {studentGrade.data && (
              <>
                <h2 className="text-lg font-bold">
                  {roster.data?.find((s) => s.id === selectedStudentId)?.name}
                </h2>
                <div className="mt-3 text-3xl font-bold text-primary">
                  {studentGrade.data.total} {es.grade.points}
                </div>
                <dl className="mt-3 space-y-2 text-sm">
                  <div className="flex justify-between">
                    <dt>📌 {es.grade.tareas}</dt>
                    <dd>
                      {studentGrade.data.tareas.evaluated
                        ? `${studentGrade.data.tareas.points} / ${studentGrade.data.tareas.weight}`
                        : es.grade.notEvaluated}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt>📝 {es.grade.examenes}</dt>
                    <dd>
                      {studentGrade.data.examenes.evaluated
                        ? `${studentGrade.data.examenes.points} / ${studentGrade.data.examenes.weight}`
                        : es.grade.notEvaluated}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt>🗣️ {es.grade.participaciones}</dt>
                    <dd>{studentGrade.data.ledger.participaciones}</dd>
                  </div>
                  {studentGrade.data.faltas.count > 0 && (
                    <div className="flex justify-between text-destructive">
                      <dt>🚫 {es.grade.faltas}</dt>
                      <dd>−{studentGrade.data.faltas.points}</dd>
                    </div>
                  )}
                </dl>
              </>
            )}
            <button
              onClick={() => setSelectedStudentId(null)}
              className="mt-5 w-full rounded-md border py-2 text-sm"
            >
              {es.grade.close}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add route to `frontend/src/App.tsx`**

```tsx
import ClassPanel from "@/pages/ClassPanel";
// ...
<Route
  path="/clases/:id"
  element={
    <RequireAuth>
      <Shell>
        <ClassPanel />
      </Shell>
    </RequireAuth>
  }
/>
```

- [ ] **Step 3: Link from `Classes.tsx` to the panel**

Read `Classes.tsx` to find the class name display, then wrap it with `<Link to={`/clases/${klass.id}`}>`.

- [ ] **Step 4: TypeScript check + commit**

```bash
cd /Users/marius/Proyectos/coding/school-app/frontend && npx tsc --noEmit
git add frontend/src/pages/ClassPanel.tsx frontend/src/App.tsx frontend/src/pages/Classes.tsx
git commit -m "feat(frontend): class panel with roster, calificaciones tabs, and session controls"
```

---

### Task 7: Pasar lista page (`/pasar-lista/:class_id/:session_id`)

**Files:**
- Create: `frontend/src/pages/PasarLista.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create `frontend/src/pages/PasarLista.tsx`**

```tsx
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useToast } from "@/components/Toaster";
import { es } from "@/strings/es";
import type { ClassDetailWithMembers, MemberOut } from "@/lib/types";

type Status = "present" | "absent" | "late";

export default function PasarLista() {
  const { class_id, session_id } = useParams<{
    class_id: string;
    session_id: string;
  }>();
  const classId = Number(class_id);
  const sessionId = Number(session_id);
  const navigate = useNavigate();
  const toast = useToast();

  const detail = useQuery({
    queryKey: ["class-detail", classId],
    queryFn: () => api<ClassDetailWithMembers>(`/api/classes/${classId}`),
    enabled: !isNaN(classId),
  });

  const activeMembers: MemberOut[] = (detail.data?.members ?? []).filter(
    (m) => m.status === "active",
  );

  const [statuses, setStatuses] = useState<Record<number, Status>>({});

  function getStatus(userId: number): Status {
    return statuses[userId] ?? "present";
  }

  function cycle(userId: number) {
    const current = getStatus(userId);
    const next: Status =
      current === "present"
        ? "absent"
        : current === "absent"
          ? "late"
          : "present";
    setStatuses((s) => ({ ...s, [userId]: next }));
  }

  const save = useMutation({
    mutationFn: () => {
      const records = activeMembers.map((m) => ({
        user_id: m.id,
        status: getStatus(m.id),
      }));
      return api<{ saved: number }>(`/api/sessions/${sessionId}/attendance`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ records }),
      });
    },
    onSuccess: () => {
      toast.show(es.asistencia.saved);
      navigate(-1);
    },
    onError: () => toast.show(es.asistencia.saveError),
  });

  function labelFor(s: Status): string {
    if (s === "present") return es.asistencia.statusPresent;
    if (s === "absent") return es.asistencia.statusAbsent;
    return es.asistencia.statusLate;
  }

  function colorFor(s: Status): string {
    if (s === "present") return "bg-green-100 text-green-800";
    if (s === "absent") return "bg-red-100 text-red-800";
    return "bg-yellow-100 text-yellow-800";
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b bg-background px-4 py-3">
        <button
          onClick={() => navigate(-1)}
          className="text-sm text-primary underline"
        >
          ← {es.asistencia.back}
        </button>
        <h1 className="font-bold">{es.asistencia.title}</h1>
        <button
          onClick={() => save.mutate()}
          disabled={save.isPending || detail.isPending}
          className="rounded-md bg-primary px-3 py-1 text-sm text-primary-foreground disabled:opacity-50"
        >
          {save.isPending ? es.asistencia.saving : es.asistencia.saveButton}
        </button>
      </header>

      <main className="flex-1 overflow-y-auto">
        {detail.isPending && (
          <p className="p-4 text-muted-foreground">{es.common.loading}</p>
        )}
        {activeMembers.length === 0 && !detail.isPending && (
          <p className="p-4 text-muted-foreground">
            {es.asistencia.emptyStudents}
          </p>
        )}
        <ul className="divide-y">
          {activeMembers.map((m) => {
            const status = getStatus(m.id);
            return (
              <li
                key={m.id}
                className="flex items-center justify-between px-4 py-4"
              >
                <div>
                  <p className="font-medium">{m.name}</p>
                  {m.username && (
                    <p className="text-xs text-muted-foreground">
                      @{m.username}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => cycle(m.id)}
                  className={`min-w-[3rem] rounded-full px-4 py-2 text-sm font-bold ${colorFor(status)}`}
                >
                  {labelFor(status)}
                </button>
              </li>
            );
          })}
        </ul>
      </main>
    </div>
  );
}
```

- [ ] **Step 2: Register route in `App.tsx`**

```tsx
import PasarLista from "@/pages/PasarLista";
// ...
<Route
  path="/pasar-lista/:class_id/:session_id"
  element={
    <RequireAuth>
      <PasarLista />
    </RequireAuth>
  }
/>
```

- [ ] **Step 3: TypeScript check + commit**

```bash
cd /Users/marius/Proyectos/coding/school-app/frontend && npx tsc --noEmit
git add frontend/src/pages/PasarLista.tsx frontend/src/App.tsx
git commit -m "feat(frontend): Pasar lista full-screen attendance-taking page"
```

---

### Task 8: Seed data

**Files:**
- Modify: `backend/seed.py`

Update the seed to include 3 students, 2 tareas, 1 examen, 1 session with absences, and participaciones. Read the existing `seed.py` first to match patterns (session creation, code generation, etc.), then replace with a comprehensive seed.

- [ ] **Step 1: Commit after rewrite**

```bash
git add backend/seed.py
git commit -m "chore(seed): Phase 3 seed with sessions, attendance, tareas, examen"
```

---

### Task 9: Close-out

- [ ] **Step 1: Full backend suite**

```bash
cd /Users/marius/Proyectos/coding/school-app/backend && python3 -m pytest -q
```

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/marius/Proyectos/coding/school-app/frontend && npx tsc --noEmit
```

- [ ] **Step 3: Update docs**

Tick Phase 3 in `planning/roadmap.md`. Add changelog entry in `planning/changelog.md`.

- [ ] **Step 4: Commit + push**

```bash
git add planning/
git commit -m "docs: close out Phase 3"
git push
```
