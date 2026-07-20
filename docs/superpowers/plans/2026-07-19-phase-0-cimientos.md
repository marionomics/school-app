# Phase 0 — Cimientos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Working skeleton of the v2 platform: monorepo, Google login, username/bio onboarding, class creation/join with schedule, deployed to Railway.

**Architecture:** Monorepo with `backend/` (FastAPI + SQLAlchemy 2 + Alembic) and `frontend/` (React + Vite + shadcn). In dev, Vite proxies `/api` to uvicorn; in prod, FastAPI serves `frontend/dist`. Session tokens live in the DB. Spec: `docs/superpowers/specs/2026-07-19-v2-platform-rebuild-design.md`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, pytest, google-auth · TypeScript, React 18, Vite, shadcn (preset `b3SkwD0Ou`), react-router-dom · PostgreSQL (prod/CI), SQLite (local) · Railway, Cloudflare R2 (later phases).

## Global Constraints

- **Mobile first:** every screen designed/QA'd at 390 px width before desktop.
- **Copy:** ALL user-facing strings live in `frontend/src/strings/es.ts`, marked as draft — Mario writes final copy. Never hardcode UI text in components.
- **Migrations:** schema changes ONLY via Alembic. Never ad-hoc ALTER TABLE, never `create_all()` in prod code paths (tests may use `create_all`).
- **Scale rule:** "una décima" (10-scale) = 1 point (100-scale). Not used in Phase 0 but constants must never contradict it.
- **Roles:** `student` default; `teacher` assigned when login email == `TEACHER_EMAIL` env.
- **Username:** regex `^[a-z0-9_]{3,20}$`, unique.
- **Schedule JSON:** list of `{"day": 0–6, "start": "HH:MM", "end": "HH:MM"}` (0 = Monday).
- **Class code:** `{PREFIX}{YEAR}{4 chars A-Z0-9}`, e.g. `MICRO2026AB3X`.
- **Class defaults:** `tareas_weight=30`, `examenes_weight=30`, `attendance_required_pct=80`.
- Commit after every task (at minimum).

---

### Task 1: Backend scaffold + health endpoint

**Files:**
- Create: `backend/requirements.txt`, `backend/app/__init__.py`, `backend/app/config.py`, `backend/app/database.py`, `backend/app/main.py`, `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`, `backend/.env.example`

**Interfaces:**
- Produces: `app.config.settings` (fields: `database_url`, `google_client_id`, `teacher_email`, `cors_origins`), `app.database.Base/engine/SessionLocal/get_db`, FastAPI `app.main.app`, pytest fixtures `db`, `client`.

- [ ] **Step 1: Create the environment and requirements**

```bash
cd backend && python3 -m venv .venv && source .venv/bin/activate
```

`backend/requirements.txt`:
```
fastapi>=0.115
uvicorn[standard]>=0.30
sqlalchemy>=2.0
alembic>=1.13
pydantic-settings>=2.4
google-auth>=2.34
requests>=2.32
psycopg[binary]>=3.2
pytest>=8.3
httpx>=0.27
```

Run: `pip install -r requirements.txt`

- [ ] **Step 2: Write config and database modules**

`backend/app/config.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./school_v2.db"
    google_client_id: str = ""
    teacher_email: str = ""
    cors_origins: str = "http://localhost:5173"

    @property
    def sqlalchemy_url(self) -> str:
        # Railway provides postgres:// URLs; SQLAlchemy+psycopg3 needs postgresql+psycopg://
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


settings = Settings()
```

`backend/app/database.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.sqlalchemy_url.startswith("sqlite") else {}
engine = create_engine(settings.sqlalchemy_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

`backend/app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI(title="Plataforma v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

`backend/.env.example`:
```
DATABASE_URL=sqlite:///./school_v2.db
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
TEACHER_EMAIL=hola@marionomics.com
CORS_ORIGINS=http://localhost:5173
```

- [ ] **Step 3: Write conftest and the failing health test**

`backend/tests/conftest.py`:
```python
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")


@pytest.fixture()
def db():
    if TEST_DB_URL.startswith("sqlite"):
        engine = create_engine(
            TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    else:
        engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(db):
    def override():
        yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

`backend/tests/test_health.py`:
```python
def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
```

- [ ] **Step 4: Run tests**

Run (from `backend/`): `pytest -v`
Expected: `test_health PASSED` (1 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "feat(backend): scaffold FastAPI app with config, database, health endpoint"
```

---

### Task 2: Alembic + User and AuthSession models + initial migration

**Files:**
- Create: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/<generated>_users_sessions.py`, `backend/app/models.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `app.models.User` (fields: `id, google_id, email, name, username, bio, avatar_url, role, grade_is_private, created_at`) and `app.models.AuthSession` (`id, user_id, token, created_at, expires_at`, relationship `user`).

- [ ] **Step 1: Write the failing model test**

`backend/tests/test_models.py`:
```python
from app.models import AuthSession, User


def test_user_defaults(db):
    user = User(google_id="g1", email="a@example.com", name="Alumno Uno")
    db.add(user)
    db.commit()
    db.refresh(user)
    assert user.role == "student"
    assert user.username is None
    assert user.bio == ""
    assert user.grade_is_private is False


def test_auth_session_links_user(db):
    user = User(google_id="g2", email="b@example.com", name="Alumno Dos")
    db.add(user)
    db.commit()
    session = AuthSession(user_id=user.id, token="tok123")
    db.add(session)
    db.commit()
    db.refresh(session)
    assert session.user.email == "b@example.com"
    assert session.expires_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 3: Write the models**

`backend/app/models.py`:
```python
from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
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
    username: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    bio: Mapped[str] = mapped_column(Text, default="")
    avatar_url: Mapped[str | None] = mapped_column(String(500))
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: 2 PASSED.

- [ ] **Step 5: Set up Alembic**

Run (from `backend/`): `alembic init alembic`

Edit `backend/alembic/env.py` — replace the `config`/`target_metadata` section so it reads:
```python
from app.config import settings
from app.database import Base
from app import models  # noqa: F401  (registers tables on Base.metadata)

config = context.config
config.set_main_option("sqlalchemy.url", settings.sqlalchemy_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
```

Generate and apply:
```bash
alembic revision --autogenerate -m "users and sessions"
alembic upgrade head
```
Expected: migration file appears in `alembic/versions/`; `school_v2.db` created with `users` and `sessions` tables.

- [ ] **Step 6: Commit**

```bash
git add backend/
git commit -m "feat(backend): User and AuthSession models with initial Alembic migration"
```

---

### Task 3: Google auth — login, sessions, /me, logout, /api/config

**Files:**
- Create: `backend/app/auth/__init__.py`, `backend/app/auth/google.py`, `backend/app/auth/sessions.py`, `backend/app/auth/deps.py`, `backend/app/schemas.py`, `backend/app/routers/__init__.py`, `backend/app/routers/auth.py`
- Modify: `backend/app/main.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `User`, `AuthSession` from Task 2.
- Produces:
  - `app.auth.google.verify_google_token(credential: str) -> dict` — returns `{"sub", "email", "name", "picture"}`, raises `ValueError` on invalid token.
  - `app.auth.sessions.create_session(db, user) -> str` (the token), `app.auth.sessions.revoke_session(db, token) -> None`.
  - `app.auth.deps.get_current_user` (FastAPI dependency → `User`, 401 otherwise), `app.auth.deps.get_current_teacher` (403 if not teacher).
  - Endpoints: `POST /api/auth/google` `{credential}` → `{token, user, needs_onboarding}`; `GET /api/auth/me` → `UserOut`; `POST /api/auth/logout` → 204; `GET /api/config` → `{google_client_id}`.
  - `app.schemas.UserOut` (`id, email, name, username, bio, avatar_url, role, grade_is_private`).
  - conftest fixtures: `student`, `teacher`, `auth_headers`, `teacher_headers`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_auth.py`:
```python
from app import models
from app.routers import auth as auth_router


def fake_verify(credential: str) -> dict:
    if credential == "bad":
        raise ValueError("invalid")
    return {
        "sub": "google-sub-1",
        "email": "nuevo@example.com",
        "name": "Nuevo Alumno",
        "picture": "https://example.com/p.jpg",
    }


def test_google_login_creates_user(client, db, monkeypatch):
    monkeypatch.setattr(auth_router, "verify_google_token", fake_verify)
    res = client.post("/api/auth/google", json={"credential": "good"})
    assert res.status_code == 200
    body = res.json()
    assert body["needs_onboarding"] is True
    assert body["user"]["email"] == "nuevo@example.com"
    assert body["user"]["role"] == "student"
    assert body["token"]
    assert db.query(models.User).count() == 1


def test_google_login_teacher_email(client, db, monkeypatch):
    monkeypatch.setattr(auth_router, "verify_google_token", fake_verify)
    monkeypatch.setattr(auth_router.settings, "teacher_email", "nuevo@example.com")
    res = client.post("/api/auth/google", json={"credential": "good"})
    assert res.json()["user"]["role"] == "teacher"


def test_google_login_invalid_token(client, monkeypatch):
    monkeypatch.setattr(auth_router, "verify_google_token", fake_verify)
    res = client.post("/api/auth/google", json={"credential": "bad"})
    assert res.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_user(client, auth_headers):
    res = client.get("/api/auth/me", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["email"] == "alumno@example.com"


def test_logout_revokes_session(client, auth_headers):
    assert client.post("/api/auth/logout", headers=auth_headers).status_code == 204
    assert client.get("/api/auth/me", headers=auth_headers).status_code == 401


def test_config_is_public(client):
    res = client.get("/api/config")
    assert res.status_code == 200
    assert "google_client_id" in res.json()
```

Append to `backend/tests/conftest.py`:
```python
from app.auth.sessions import create_session
from app.models import User


@pytest.fixture()
def student(db):
    user = User(google_id="g-student", email="alumno@example.com", name="Alumno Uno")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def teacher(db):
    user = User(
        google_id="g-teacher", email="profe@example.com", name="Profe", role="teacher"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def auth_headers(db, student):
    return {"Authorization": f"Bearer {create_session(db, student)}"}


@pytest.fixture()
def teacher_headers(db, teacher):
    return {"Authorization": f"Bearer {create_session(db, teacher)}"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.auth'`

- [ ] **Step 3: Implement auth modules and router**

`backend/app/auth/__init__.py`: empty file.

`backend/app/auth/google.py`:
```python
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import settings


def verify_google_token(credential: str) -> dict:
    """Verify a Google ID token. Returns {sub, email, name, picture}; raises ValueError."""
    info = id_token.verify_oauth2_token(
        credential, google_requests.Request(), settings.google_client_id
    )
    return {
        "sub": info["sub"],
        "email": info["email"],
        "name": info.get("name", info["email"]),
        "picture": info.get("picture"),
    }
```

`backend/app/auth/sessions.py`:
```python
import secrets

from sqlalchemy.orm import Session

from app.models import AuthSession, User


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(user_id=user.id, token=token))
    db.commit()
    return token


def revoke_session(db: Session, token: str) -> None:
    db.query(AuthSession).filter(AuthSession.token == token).delete()
    db.commit()
```

`backend/app/auth/deps.py`:
```python
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuthSession, User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticado")
    token = header.removeprefix("Bearer ")
    session = db.query(AuthSession).filter(AuthSession.token == token).first()
    if session is None:
        raise HTTPException(status_code=401, detail="Sesión inválida")
    expires = session.expires_at
    if expires.tzinfo is None:  # SQLite drops tzinfo
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Sesión expirada")
    return session.user


def get_current_teacher(user: User = Depends(get_current_user)) -> User:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Solo para el profesor")
    return user
```

`backend/app/schemas.py`:
```python
from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    username: str | None
    bio: str
    avatar_url: str | None
    role: str
    grade_is_private: bool


class GoogleLoginRequest(BaseModel):
    credential: str


class AuthResponse(BaseModel):
    token: str
    user: UserOut
    needs_onboarding: bool
```

`backend/app/routers/__init__.py`: empty file.

`backend/app/routers/auth.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.google import verify_google_token
from app.auth.sessions import create_session, revoke_session
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import AuthResponse, GoogleLoginRequest, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/google", response_model=AuthResponse)
def login_google(body: GoogleLoginRequest, db: Session = Depends(get_db)):
    try:
        info = verify_google_token(body.credential)
    except ValueError:
        raise HTTPException(status_code=401, detail="Token de Google inválido")

    user = db.query(User).filter(User.google_id == info["sub"]).first()
    if user is None:
        user = User(
            google_id=info["sub"],
            email=info["email"],
            name=info["name"],
            avatar_url=info.get("picture"),
        )
        db.add(user)
    if settings.teacher_email and info["email"] == settings.teacher_email:
        user.role = "teacher"
    db.commit()
    db.refresh(user)
    token = create_session(db, user)
    return AuthResponse(
        token=token, user=UserOut.model_validate(user), needs_onboarding=user.username is None
    )


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)):
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        revoke_session(db, header.removeprefix("Bearer "))
```

In `backend/app/main.py` add after the CORS middleware block:
```python
from app.routers import auth as auth_router

app.include_router(auth_router.router)


@app.get("/api/config")
def config():
    return {"google_client_id": settings.google_client_id}
```
(Note: `get_current_user` import lives in `app.auth.deps`; `/api/auth/me` is added here too:)
```python
from fastapi import Depends

from app.auth.deps import get_current_user
from app.models import User
from app.schemas import UserOut


@app.get("/api/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest -v`
Expected: all tests pass (health, models, auth — 10 total).

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "feat(backend): Google auth with DB sessions, /me, logout, /api/config"
```

---

### Task 4: Onboarding — username + bio

**Files:**
- Create: `backend/app/routers/users.py`
- Modify: `backend/app/main.py`, `backend/app/schemas.py`
- Test: `backend/tests/test_users.py`

**Interfaces:**
- Consumes: `get_current_user`, `UserOut`, fixtures from Task 3.
- Produces: `PATCH /api/users/me` body `{username?, bio?}` → `UserOut` (422 invalid format, 409 taken); `GET /api/users/username-available?u=foo` → `{available: bool}` (public shape, requires auth).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_users.py`:
```python
from app.models import User


def test_set_username_and_bio(client, auth_headers):
    res = client.patch(
        "/api/users/me",
        json={"username": "alumno_uno", "bio": "Economista en formación"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["username"] == "alumno_uno"
    assert res.json()["bio"] == "Economista en formación"


def test_username_format_rejected(client, auth_headers):
    for bad in ["Ab", "with spaces", "ñoño", "a" * 21, "UPPER"]:
        res = client.patch("/api/users/me", json={"username": bad}, headers=auth_headers)
        assert res.status_code == 422, bad


def test_username_taken(client, db, auth_headers):
    other = User(google_id="g-x", email="x@example.com", name="X", username="tomado")
    db.add(other)
    db.commit()
    res = client.patch("/api/users/me", json={"username": "tomado"}, headers=auth_headers)
    assert res.status_code == 409


def test_username_available(client, db, auth_headers):
    other = User(google_id="g-y", email="y@example.com", name="Y", username="ocupado")
    db.add(other)
    db.commit()
    res = client.get("/api/users/username-available?u=ocupado", headers=auth_headers)
    assert res.json() == {"available": False}
    res = client.get("/api/users/username-available?u=libre", headers=auth_headers)
    assert res.json() == {"available": True}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_users.py -v`
Expected: FAIL — 404s (`/api/users/me` not registered).

- [ ] **Step 3: Implement**

Append to `backend/app/schemas.py`:
```python
from pydantic import Field


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, pattern=r"^[a-z0-9_]{3,20}$")
    bio: str | None = Field(default=None, max_length=500)
```

`backend/app/routers/users.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.patch("/me", response_model=UserOut)
def update_me(
    body: UserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.username is not None and body.username != user.username:
        taken = db.query(User).filter(User.username == body.username).first()
        if taken is not None:
            raise HTTPException(status_code=409, detail="Ese username ya está ocupado")
        user.username = body.username
    if body.bio is not None:
        user.bio = body.bio
    db.commit()
    db.refresh(user)
    return user


@router.get("/username-available")
def username_available(
    u: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exists = db.query(User).filter(User.username == u).first() is not None
    return {"available": not exists}
```

In `backend/app/main.py`, next to the auth router include:
```python
from app.routers import users as users_router

app.include_router(users_router.router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest -v` — Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "feat(backend): onboarding endpoints — username with validation, bio"
```

---

### Task 5: Class + Enrollment models, migration, code generator

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/app/services/__init__.py`, `backend/app/services/class_codes.py`, `backend/alembic/versions/<generated>_classes_enrollments.py`
- Test: `backend/tests/test_class_codes.py`

**Interfaces:**
- Consumes: `Base`, `User`.
- Produces: `app.models.Class` (`id, name, code, teacher_id, start_date, end_date, schedule_json, tareas_weight, examenes_weight, attendance_required_pct, created_at`), `app.models.Enrollment` (`id, user_id, class_id, status, joined_at`, unique `(user_id, class_id)`), `app.services.class_codes.generate_code(db, prefix: str) -> str`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_class_codes.py`:
```python
import re
from datetime import date

from app.models import Class, Enrollment, User
from app.services.class_codes import generate_code


def _teacher(db):
    t = User(google_id="g-t", email="t@example.com", name="T", role="teacher")
    db.add(t)
    db.commit()
    return t


def test_code_format(db):
    code = generate_code(db, "micro")
    assert re.fullmatch(r"MICRO\d{4}[A-Z0-9]{4}", code)


def test_code_avoids_collisions(db, monkeypatch):
    t = _teacher(db)
    existing = Class(
        name="X", code="MICRO2026AAAA", teacher_id=t.id,
        start_date=date(2026, 8, 1), end_date=date(2026, 12, 1), schedule_json=[],
    )
    db.add(existing)
    db.commit()
    import app.services.class_codes as cc
    calls = iter(["AAAA", "BBBB"])
    monkeypatch.setattr(cc, "_random_suffix", lambda: next(calls))
    code = generate_code(db, "MICRO")
    assert code.endswith("BBBB")


def test_enrollment_unique(db):
    t = _teacher(db)
    c = Class(
        name="Micro", code="MICRO2026ZZZZ", teacher_id=t.id,
        start_date=date(2026, 8, 1), end_date=date(2026, 12, 1), schedule_json=[],
    )
    s = User(google_id="g-s", email="s@example.com", name="S")
    db.add_all([c, s])
    db.commit()
    e = Enrollment(user_id=s.id, class_id=c.id)
    db.add(e)
    db.commit()
    assert e.status == "active"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_class_codes.py -v`
Expected: FAIL — `ImportError` (no `Class` in models).

- [ ] **Step 3: Implement models and generator**

Append to `backend/app/models.py`:
```python
from datetime import date

from sqlalchemy import Date, Integer, JSON, UniqueConstraint


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
```

`backend/app/services/__init__.py`: empty file.

`backend/app/services/class_codes.py`:
```python
import secrets
import string
from datetime import date

from sqlalchemy.orm import Session

from app.models import Class

_ALPHABET = string.ascii_uppercase + string.digits


def _random_suffix() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(4))


def generate_code(db: Session, prefix: str) -> str:
    prefix = "".join(ch for ch in prefix.upper() if ch.isalnum()) or "CLASE"
    year = date.today().year
    while True:
        code = f"{prefix}{year}{_random_suffix()}"
        if db.query(Class).filter(Class.code == code).first() is None:
            return code
```

- [ ] **Step 4: Run tests, generate migration**

Run: `pytest tests/test_class_codes.py -v` — Expected: 3 PASSED.

```bash
alembic revision --autogenerate -m "classes and enrollments"
alembic upgrade head
```
Expected: new migration in `alembic/versions/`, applies cleanly.

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "feat(backend): Class and Enrollment models with code generator"
```

---

### Task 6: Classes endpoints — create, join, mine, detail

**Files:**
- Create: `backend/app/routers/classes.py`
- Modify: `backend/app/schemas.py`, `backend/app/main.py`
- Test: `backend/tests/test_classes.py`

**Interfaces:**
- Consumes: `Class`, `Enrollment`, `generate_code`, `get_current_user`, `get_current_teacher`.
- Produces:
  - `POST /api/classes` (teacher) body `ClassCreate {name, code_prefix?, start_date, end_date, schedule, tareas_weight?, examenes_weight?}` → `ClassOut`
  - `POST /api/classes/join` body `{code}` → `ClassOut` (404 bad code, 409 already enrolled)
  - `GET /api/classes/mine` → `{teaching: ClassOut[], enrolled: ClassOut[]}`
  - `GET /api/classes/{class_id}` → `ClassDetail` (adds `members: MemberOut[]`; teacher or enrolled only, else 403)
  - `app.schemas.ScheduleBlock {day: int(0-6), start: "HH:MM", end: "HH:MM"}`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_classes.py`:
```python
CLASS_PAYLOAD = {
    "name": "Microeconomía",
    "code_prefix": "MICRO",
    "start_date": "2026-08-17",
    "end_date": "2026-12-04",
    "schedule": [{"day": 0, "start": "10:00", "end": "11:00"}],
}


def test_create_requires_teacher(client, auth_headers):
    res = client.post("/api/classes", json=CLASS_PAYLOAD, headers=auth_headers)
    assert res.status_code == 403


def test_create_class(client, teacher_headers):
    res = client.post("/api/classes", json=CLASS_PAYLOAD, headers=teacher_headers)
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Microeconomía"
    assert body["code"].startswith("MICRO")
    assert body["tareas_weight"] == 30
    assert body["schedule"] == CLASS_PAYLOAD["schedule"]


def test_schedule_validation(client, teacher_headers):
    bad = dict(CLASS_PAYLOAD, schedule=[{"day": 9, "start": "10:00", "end": "11:00"}])
    assert client.post("/api/classes", json=bad, headers=teacher_headers).status_code == 422
    bad = dict(CLASS_PAYLOAD, schedule=[{"day": 0, "start": "25:00", "end": "11:00"}])
    assert client.post("/api/classes", json=bad, headers=teacher_headers).status_code == 422


def test_join_and_mine(client, auth_headers, teacher_headers):
    code = client.post("/api/classes", json=CLASS_PAYLOAD, headers=teacher_headers).json()["code"]

    res = client.post("/api/classes/join", json={"code": code}, headers=auth_headers)
    assert res.status_code == 200

    res = client.post("/api/classes/join", json={"code": code}, headers=auth_headers)
    assert res.status_code == 409

    res = client.post("/api/classes/join", json={"code": "NOPE2026XXXX"}, headers=auth_headers)
    assert res.status_code == 404

    mine = client.get("/api/classes/mine", headers=auth_headers).json()
    assert len(mine["enrolled"]) == 1 and mine["teaching"] == []

    mine = client.get("/api/classes/mine", headers=teacher_headers).json()
    assert len(mine["teaching"]) == 1


def test_detail_membership(client, db, auth_headers, teacher_headers):
    created = client.post("/api/classes", json=CLASS_PAYLOAD, headers=teacher_headers).json()
    client.post("/api/classes/join", json={"code": created["code"]}, headers=auth_headers)

    res = client.get(f"/api/classes/{created['id']}", headers=auth_headers)
    assert res.status_code == 200
    assert len(res.json()["members"]) == 1

    from app.auth.sessions import create_session
    from app.models import User

    outsider = User(google_id="g-out", email="out@example.com", name="Out")
    db.add(outsider)
    db.commit()
    headers = {"Authorization": f"Bearer {create_session(db, outsider)}"}
    assert client.get(f"/api/classes/{created['id']}", headers=headers).status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_classes.py -v`
Expected: FAIL — 404 (routes not registered).

- [ ] **Step 3: Implement schemas and router**

Append to `backend/app/schemas.py`:
```python
from datetime import date


class ScheduleBlock(BaseModel):
    day: int = Field(ge=0, le=6)  # 0 = lunes
    start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code_prefix: str = Field(default="CLASE", max_length=10)
    start_date: date
    end_date: date
    schedule: list[ScheduleBlock] = []
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
    schedule: list[ScheduleBlock] = Field(validation_alias="schedule_json")
    tareas_weight: int
    examenes_weight: int
    attendance_required_pct: int


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    username: str | None
    avatar_url: str | None
    status: str


class ClassDetail(ClassOut):
    members: list[MemberOut] = []


class JoinRequest(BaseModel):
    code: str


class MyClasses(BaseModel):
    teaching: list[ClassOut]
    enrolled: list[ClassOut]
```

`backend/app/routers/classes.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_teacher, get_current_user
from app.database import get_db
from app.models import Class, Enrollment, User
from app.schemas import ClassCreate, ClassDetail, ClassOut, JoinRequest, MemberOut, MyClasses
from app.services.class_codes import generate_code

router = APIRouter(prefix="/api/classes", tags=["classes"])


@router.post("", response_model=ClassOut, status_code=201)
def create_class(
    body: ClassCreate,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    klass = Class(
        name=body.name,
        code=generate_code(db, body.code_prefix),
        teacher_id=teacher.id,
        start_date=body.start_date,
        end_date=body.end_date,
        schedule_json=[b.model_dump() for b in body.schedule],
        tareas_weight=body.tareas_weight,
        examenes_weight=body.examenes_weight,
    )
    db.add(klass)
    db.commit()
    db.refresh(klass)
    return klass


@router.post("/join", response_model=ClassOut)
def join_class(
    body: JoinRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    klass = db.query(Class).filter(Class.code == body.code.strip().upper()).first()
    if klass is None:
        raise HTTPException(status_code=404, detail="Código de clase no encontrado")
    exists = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == user.id, Enrollment.class_id == klass.id)
        .first()
    )
    if exists is not None:
        raise HTTPException(status_code=409, detail="Ya estás en esta clase")
    db.add(Enrollment(user_id=user.id, class_id=klass.id))
    db.commit()
    return klass


@router.get("/mine", response_model=MyClasses)
def my_classes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    teaching = db.query(Class).filter(Class.teacher_id == user.id).all()
    enrolled = (
        db.query(Class)
        .join(Enrollment, Enrollment.class_id == Class.id)
        .filter(Enrollment.user_id == user.id)
        .all()
    )
    return MyClasses(
        teaching=[ClassOut.model_validate(c) for c in teaching],
        enrolled=[ClassOut.model_validate(c) for c in enrolled],
    )


@router.get("/{class_id}", response_model=ClassDetail)
def class_detail(
    class_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    klass = db.get(Class, class_id)
    if klass is None:
        raise HTTPException(status_code=404, detail="Clase no encontrada")
    enrollments = db.query(Enrollment).filter(Enrollment.class_id == class_id).all()
    is_member = any(e.user_id == user.id for e in enrollments)
    if klass.teacher_id != user.id and not is_member:
        raise HTTPException(status_code=403, detail="No perteneces a esta clase")
    detail = ClassDetail.model_validate(klass)
    detail.members = [
        MemberOut(
            id=e.user.id,
            name=e.user.name,
            username=e.user.username,
            avatar_url=e.user.avatar_url,
            status=e.status,
        )
        for e in enrollments
    ]
    return detail
```

In `backend/app/main.py`, register:
```python
from app.routers import classes as classes_router

app.include_router(classes_router.router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest -v` — Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "feat(backend): classes endpoints — create, join by code, mine, detail"
```

---

### Task 7: Frontend scaffold — shadcn preset, proxy, strings, api client

**Files:**
- Create: `frontend/` (generated by shadcn preset), `frontend/src/strings/es.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/types.ts`
- Modify: `frontend/vite.config.ts`

**Interfaces:**
- Produces: `api<T>(path, init?)` fetch wrapper (attaches `Authorization: Bearer`, throws `ApiError{status, message}`), `getToken/setToken/clearToken`, `es` strings object, TS types `User`, `ClassOut`, `MyClasses`.

- [ ] **Step 1: Scaffold with the preset (from repo root)**

```bash
npx shadcn@latest init --preset b3SkwD0Ou --template vite
```
When prompted for the project directory/name, use `frontend`. Then:
```bash
cd frontend && npm install && npm run dev
```
Expected: Vite dev server on http://localhost:5173 with the preset's starter page. Stop it.

If the preset command fails (network/registry), fall back to `npm create vite@latest frontend -- --template react-ts`, then `npx shadcn@latest init` inside it, and note the deviation in the commit message.

- [ ] **Step 2: Add the dev proxy**

In `frontend/vite.config.ts`, add to the exported config:
```ts
server: {
  proxy: {
    "/api": "http://localhost:8000",
  },
},
```

- [ ] **Step 3: Add router dependency**

```bash
npm install react-router-dom
```

- [ ] **Step 4: Create strings, types, and the api client**

`frontend/src/strings/es.ts`:
```ts
// BORRADOR DE COPY — Mario escribe la versión final de todos los textos.
export const es = {
  appName: "Plataforma de clases",
  login: {
    title: "Bienvenido",
    subtitle: "Inicia sesión con tu cuenta de Google",
    error: "No se pudo iniciar sesión. Intenta de nuevo.",
  },
  onboarding: {
    title: "Crea tu perfil",
    usernameLabel: "Username",
    usernameHint: "3-20 caracteres: letras minúsculas, números y _",
    usernameTaken: "Ese username ya está ocupado",
    bioLabel: "Bio",
    bioPlaceholder: "Cuéntanos quién eres…",
    submit: "Continuar",
  },
  home: {
    feedComingSoon: "El feed llega en la Fase 1 🚧",
  },
  nav: {
    home: "Inicio",
    profile: "Perfil",
    classes: "Mis clases",
    settings: "Configuración",
    logout: "Cerrar sesión",
  },
  classes: {
    title: "Mis clases",
    teaching: "Clases que doy",
    enrolled: "Clases donde estoy",
    empty: "Aún no estás en ninguna clase.",
    create: "Crear clase",
    join: "Unirme con código",
    codeLabel: "Código de la clase",
    joinSubmit: "Unirme",
    name: "Nombre de la clase",
    prefix: "Prefijo del código (ej. MICRO)",
    startDate: "Fecha de inicio",
    endDate: "Fecha de fin",
    schedule: "Horario",
    addBlock: "Agregar horario",
    createSubmit: "Crear",
    copyLink: "Copiar link de invitación",
    linkCopied: "¡Link copiado!",
    days: ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
  },
} as const;
```

`frontend/src/lib/types.ts`:
```ts
export interface User {
  id: number;
  email: string;
  name: string;
  username: string | null;
  bio: string;
  avatar_url: string | null;
  role: "student" | "teacher";
  grade_is_private: boolean;
}

export interface ScheduleBlock {
  day: number; // 0 = lunes
  start: string; // "HH:MM"
  end: string;
}

export interface ClassOut {
  id: number;
  name: string;
  code: string;
  teacher_id: number;
  start_date: string;
  end_date: string;
  schedule: ScheduleBlock[];
  tareas_weight: number;
  examenes_weight: number;
  attendance_required_pct: number;
}

export interface MyClasses {
  teaching: ClassOut[];
  enrolled: ClassOut[];
}

export interface AuthResponse {
  token: string;
  user: User;
  needs_onboarding: boolean;
}
```

`frontend/src/lib/api.ts`:
```ts
const TOKEN_KEY = "session_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, { ...init, headers });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
```

- [ ] **Step 5: Verify build and commit**

Run: `npm run build`
Expected: builds without TypeScript errors.

```bash
git add frontend/ && git commit -m "feat(frontend): scaffold Vite+shadcn app with api client, types, es strings"
```

---

### Task 8: Frontend auth — AuthProvider, login page, route guard

**Files:**
- Create: `frontend/src/lib/auth.tsx`, `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/App.tsx` (or the preset's root component), `frontend/src/main.tsx`, `frontend/index.html`

**Interfaces:**
- Consumes: `api`, `setToken`, `clearToken`, `es`, types from Task 7; backend endpoints from Tasks 3–4.
- Produces: `<AuthProvider>`, `useAuth() => { user: User | null; loading: boolean; refresh(): Promise<void>; logout(): Promise<void> }`, `<RequireAuth>` wrapper, route `/login`.

- [ ] **Step 1: Load Google Identity Services**

In `frontend/index.html` `<head>`:
```html
<script src="https://accounts.google.com/gsi/client" async defer></script>
```
(No SRI hash on purpose: Google rotates this script continuously and documents loading it live from their origin — a pinned `integrity` hash would break login when they update it. This is the one sanctioned external script; everything else must be bundled.)

- [ ] **Step 2: Write the auth context**

`frontend/src/lib/auth.tsx`:
```tsx
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, clearToken, getToken } from "./api";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  refresh: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api<User>("/api/auth/me"));
    } catch {
      clearToken();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } finally {
      clearToken();
      setUser(null);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <AuthContext.Provider value={{ user, loading, refresh, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
```

- [ ] **Step 3: Write the login page**

`frontend/src/pages/Login.tsx`:
```tsx
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { es } from "@/strings/es";
import type { AuthResponse } from "@/lib/types";

declare global {
  interface Window {
    google?: any;
  }
}

export default function Login() {
  const buttonRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState(false);
  const navigate = useNavigate();
  const { refresh } = useAuth();

  useEffect(() => {
    let cancelled = false;
    async function init() {
      const { google_client_id } = await api<{ google_client_id: string }>("/api/config");
      const google = window.google;
      if (cancelled || !google || !buttonRef.current) return;
      google.accounts.id.initialize({
        client_id: google_client_id,
        callback: async (response: { credential: string }) => {
          try {
            const auth = await api<AuthResponse>("/api/auth/google", {
              method: "POST",
              body: JSON.stringify({ credential: response.credential }),
            });
            setToken(auth.token);
            await refresh();
            navigate(auth.needs_onboarding ? "/onboarding" : "/", { replace: true });
          } catch {
            setError(true);
          }
        },
      });
      google.accounts.id.renderButton(buttonRef.current, { theme: "outline", size: "large" });
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, [navigate, refresh]);

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-6 p-6">
      <h1 className="text-2xl font-bold">{es.login.title}</h1>
      <p className="text-muted-foreground">{es.login.subtitle}</p>
      <div ref={buttonRef} />
      {error && <p className="text-destructive">{es.login.error}</p>}
    </main>
  );
}
```

- [ ] **Step 4: Wire the router and guard**

Replace the preset's root component content in `frontend/src/App.tsx`:
```tsx
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "@/lib/auth";
import Login from "@/pages/Login";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  if (!user.username && location.pathname !== "/onboarding")
    return <Navigate to="/onboarding" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <div className="p-6">home placeholder — Task 10</div>
              </RequireAuth>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
```
Ensure `frontend/src/main.tsx` renders `<App />`.

- [ ] **Step 5: Verify manually and commit**

Run backend (`cd backend && uvicorn app.main:app --reload`) with a real `GOOGLE_CLIENT_ID` in `backend/.env`, and `cd frontend && npm run dev`. In a phone-sized viewport (390 px): visiting `/` redirects to `/login`; the Google button renders; logging in redirects to `/onboarding` (username is null). `npm run build` passes.

```bash
git add frontend/ && git commit -m "feat(frontend): Google login, auth context, route guard"
```

---

### Task 9: Onboarding page — username + bio

**Files:**
- Create: `frontend/src/pages/Onboarding.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `api`, `useAuth`, `es`; `PATCH /api/users/me`, `GET /api/users/username-available` from Task 4.
- Produces: route `/onboarding`.

- [ ] **Step 1: Write the page**

`frontend/src/pages/Onboarding.tsx`:
```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { es } from "@/strings/es";
import type { User } from "@/lib/types";

const USERNAME_RE = /^[a-z0-9_]{3,20}$/;

export default function Onboarding() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [bio, setBio] = useState("");
  const [available, setAvailable] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user?.username) navigate("/", { replace: true });
  }, [user, navigate]);

  useEffect(() => {
    setAvailable(null);
    if (!USERNAME_RE.test(username)) return;
    const t = setTimeout(async () => {
      const res = await api<{ available: boolean }>(
        `/api/users/username-available?u=${encodeURIComponent(username)}`,
      );
      setAvailable(res.available);
    }, 300);
    return () => clearTimeout(t);
  }, [username]);

  const valid = USERNAME_RE.test(username) && available !== false;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setSaving(true);
    setError(null);
    try {
      await api<User>("/api/users/me", {
        method: "PATCH",
        body: JSON.stringify({ username, bio }),
      });
      await refresh();
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError && err.status === 409 ? es.onboarding.usernameTaken : String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-4 p-6">
      <h1 className="text-2xl font-bold">{es.onboarding.title}</h1>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1">
          <span className="font-medium">{es.onboarding.usernameLabel}</span>
          <input
            className="rounded-md border px-3 py-2"
            value={username}
            onChange={(e) => setUsername(e.target.value.toLowerCase())}
            autoFocus
          />
          <span className="text-sm text-muted-foreground">{es.onboarding.usernameHint}</span>
          {available === false && (
            <span className="text-sm text-destructive">{es.onboarding.usernameTaken}</span>
          )}
        </label>
        <label className="flex flex-col gap-1">
          <span className="font-medium">{es.onboarding.bioLabel}</span>
          <textarea
            className="min-h-24 rounded-md border px-3 py-2"
            placeholder={es.onboarding.bioPlaceholder}
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            maxLength={500}
          />
        </label>
        {error && <p className="text-destructive">{error}</p>}
        <button
          type="submit"
          disabled={!valid || saving}
          className="rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground disabled:opacity-50"
        >
          {es.onboarding.submit}
        </button>
      </form>
    </main>
  );
}
```

- [ ] **Step 2: Register the route**

In `frontend/src/App.tsx` add:
```tsx
import Onboarding from "@/pages/Onboarding";
// inside <Routes>:
<Route
  path="/onboarding"
  element={
    <RequireAuth>
      <Onboarding />
    </RequireAuth>
  }
/>
```

- [ ] **Step 3: Verify and commit**

Manual (390 px viewport): fresh login lands on `/onboarding`; a taken username shows the message; valid submit lands on `/`. `npm run build` passes.

```bash
git add frontend/ && git commit -m "feat(frontend): onboarding page with username availability check"
```

---

### Task 10: App shell — bottom bar, sidebar, home placeholder

**Files:**
- Create: `frontend/src/components/Shell.tsx`, `frontend/src/pages/Home.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `useAuth`, `es`.
- Produces: `<Shell>` layout (top bar + sidebar sheet + bottom nav) wrapping all authed pages; route `/` renders `Home` inside `Shell`.

- [ ] **Step 1: Write the shell**

`frontend/src/components/Shell.tsx`:
```tsx
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { es } from "@/strings/es";

export default function Shell({ children }: { children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-20 flex items-center justify-between border-b bg-background px-4 py-3">
        <button aria-label="menu" onClick={() => setMenuOpen(true)} className="text-xl">
          ☰
        </button>
        <span className="font-bold">{es.appName}</span>
        <span className="w-6" />
      </header>

      {menuOpen && (
        <div className="fixed inset-0 z-30 flex">
          <nav className="flex w-72 flex-col gap-1 border-r bg-background p-4">
            <p className="mb-2 font-bold">@{user?.username}</p>
            <Link to="/clases" className="rounded-md px-3 py-2 hover:bg-accent" onClick={() => setMenuOpen(false)}>
              {es.nav.classes}
            </Link>
            <button onClick={handleLogout} className="mt-auto rounded-md px-3 py-2 text-left text-destructive hover:bg-accent">
              {es.nav.logout}
            </button>
          </nav>
          <div className="flex-1 bg-black/40" onClick={() => setMenuOpen(false)} />
        </div>
      )}

      <main className="flex-1 pb-16">{children}</main>

      <nav className="fixed inset-x-0 bottom-0 z-20 flex items-center justify-around border-t bg-background py-2">
        <Link to="/" aria-label={es.nav.home} className="p-2 text-xl">
          🏠
        </Link>
        <button aria-label="crear" disabled className="p-2 text-xl opacity-40">
          ➕
        </button>
        <Link to="/onboarding" aria-label={es.nav.profile} className="p-2 text-xl">
          👤
        </Link>
      </nav>
    </div>
  );
}
```
(Phase 0 shell is deliberately plain — icons/polish come with the feed in Phase 1. The ➕ is disabled until the composer exists.)

`frontend/src/pages/Home.tsx`:
```tsx
import { es } from "@/strings/es";

export default function Home() {
  return (
    <div className="flex flex-col items-center gap-4 p-10 text-center text-muted-foreground">
      <p className="text-4xl">🏗️</p>
      <p>{es.home.feedComingSoon}</p>
    </div>
  );
}
```

- [ ] **Step 2: Use it for `/`**

In `frontend/src/App.tsx`, replace the `/` route element:
```tsx
import Shell from "@/components/Shell";
import Home from "@/pages/Home";
// ...
<Route
  path="/"
  element={
    <RequireAuth>
      <Shell>
        <Home />
      </Shell>
    </RequireAuth>
  }
/>
```

- [ ] **Step 3: Verify and commit**

Manual (390 px): bottom bar fixed, sidebar opens/closes, logout returns to `/login`. `npm run build` passes.

```bash
git add frontend/ && git commit -m "feat(frontend): app shell with sidebar, bottom nav, home placeholder"
```

---

### Task 11: Classes UI — list, create, join, invite link

**Files:**
- Create: `frontend/src/pages/Classes.tsx`, `frontend/src/pages/JoinByLink.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `api`, `useAuth`, `es`, `MyClasses`, `ClassOut`, `ScheduleBlock`; endpoints from Task 6.
- Produces: routes `/clases` and `/join/:code`. Invite link format: `{origin}/join/{code}`.

- [ ] **Step 1: Write the classes page**

`frontend/src/pages/Classes.tsx`:
```tsx
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { es } from "@/strings/es";
import type { ClassOut, MyClasses, ScheduleBlock } from "@/lib/types";

const EMPTY_BLOCK: ScheduleBlock = { day: 0, start: "10:00", end: "11:00" };

function ClassCard({ klass }: { klass: ClassOut }) {
  const [copied, setCopied] = useState(false);

  async function copyLink() {
    await navigator.clipboard.writeText(`${window.location.origin}/join/${klass.code}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <span className="font-semibold">{klass.name}</span>
        <code className="rounded bg-muted px-2 py-0.5 text-sm">{klass.code}</code>
      </div>
      <p className="text-sm text-muted-foreground">
        {klass.start_date} → {klass.end_date}
      </p>
      <button onClick={copyLink} className="self-start text-sm text-primary underline">
        {copied ? es.classes.linkCopied : es.classes.copyLink}
      </button>
    </div>
  );
}

export default function Classes() {
  const { user } = useAuth();
  const [mine, setMine] = useState<MyClasses | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showJoin, setShowJoin] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [prefix, setPrefix] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [schedule, setSchedule] = useState<ScheduleBlock[]>([EMPTY_BLOCK]);
  const [joinCode, setJoinCode] = useState("");

  const load = useCallback(async () => {
    setMine(await api<MyClasses>("/api/classes/mine"));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createClass(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/api/classes", {
        method: "POST",
        body: JSON.stringify({
          name,
          code_prefix: prefix || "CLASE",
          start_date: startDate,
          end_date: endDate,
          schedule,
        }),
      });
      setShowCreate(false);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  async function joinClass(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/api/classes/join", {
        method: "POST",
        body: JSON.stringify({ code: joinCode }),
      });
      setShowJoin(false);
      setJoinCode("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  function updateBlock(i: number, patch: Partial<ScheduleBlock>) {
    setSchedule((blocks) => blocks.map((b, j) => (j === i ? { ...b, ...patch } : b)));
  }

  if (!mine) return <div className="p-6 text-muted-foreground">…</div>;

  const isTeacher = user?.role === "teacher";
  const empty = mine.teaching.length === 0 && mine.enrolled.length === 0;

  return (
    <div className="mx-auto flex max-w-md flex-col gap-4 p-4">
      <h1 className="text-xl font-bold">{es.classes.title}</h1>

      <div className="flex gap-2">
        {isTeacher && (
          <button onClick={() => setShowCreate(!showCreate)} className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground">
            {es.classes.create}
          </button>
        )}
        <button onClick={() => setShowJoin(!showJoin)} className="rounded-md border px-3 py-2 text-sm">
          {es.classes.join}
        </button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {showJoin && (
        <form onSubmit={joinClass} className="flex gap-2">
          <input
            className="flex-1 rounded-md border px-3 py-2"
            placeholder={es.classes.codeLabel}
            value={joinCode}
            onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
          />
          <button className="rounded-md bg-primary px-3 py-2 text-primary-foreground">
            {es.classes.joinSubmit}
          </button>
        </form>
      )}

      {showCreate && (
        <form onSubmit={createClass} className="flex flex-col gap-2 rounded-lg border p-4">
          <input className="rounded-md border px-3 py-2" placeholder={es.classes.name} value={name} onChange={(e) => setName(e.target.value)} required />
          <input className="rounded-md border px-3 py-2" placeholder={es.classes.prefix} value={prefix} onChange={(e) => setPrefix(e.target.value.toUpperCase())} />
          <label className="text-sm">
            {es.classes.startDate}
            <input type="date" className="w-full rounded-md border px-3 py-2" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
          </label>
          <label className="text-sm">
            {es.classes.endDate}
            <input type="date" className="w-full rounded-md border px-3 py-2" value={endDate} onChange={(e) => setEndDate(e.target.value)} required />
          </label>
          <span className="text-sm font-medium">{es.classes.schedule}</span>
          {schedule.map((block, i) => (
            <div key={i} className="flex items-center gap-2">
              <select className="rounded-md border px-2 py-2" value={block.day} onChange={(e) => updateBlock(i, { day: Number(e.target.value) })}>
                {es.classes.days.map((d, di) => (
                  <option key={di} value={di}>{d}</option>
                ))}
              </select>
              <input type="time" className="rounded-md border px-2 py-2" value={block.start} onChange={(e) => updateBlock(i, { start: e.target.value })} />
              <input type="time" className="rounded-md border px-2 py-2" value={block.end} onChange={(e) => updateBlock(i, { end: e.target.value })} />
            </div>
          ))}
          <button type="button" onClick={() => setSchedule((s) => [...s, EMPTY_BLOCK])} className="self-start text-sm text-primary underline">
            {es.classes.addBlock}
          </button>
          <button type="submit" className="rounded-md bg-primary px-3 py-2 text-primary-foreground">
            {es.classes.createSubmit}
          </button>
        </form>
      )}

      {empty && <p className="text-muted-foreground">{es.classes.empty}</p>}

      {mine.teaching.length > 0 && (
        <>
          <h2 className="font-semibold">{es.classes.teaching}</h2>
          {mine.teaching.map((k) => <ClassCard key={k.id} klass={k} />)}
        </>
      )}
      {mine.enrolled.length > 0 && (
        <>
          <h2 className="font-semibold">{es.classes.enrolled}</h2>
          {mine.enrolled.map((k) => <ClassCard key={k.id} klass={k} />)}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Write the join-by-link page**

`frontend/src/pages/JoinByLink.tsx`:
```tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "@/lib/api";

export default function JoinByLink() {
  const { code } = useParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function join() {
      try {
        await api("/api/classes/join", { method: "POST", body: JSON.stringify({ code }) });
        navigate("/clases", { replace: true });
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          navigate("/clases", { replace: true }); // already in — fine
        } else {
          setError(err instanceof ApiError ? err.message : String(err));
        }
      }
    }
    void join();
  }, [code, navigate]);

  return <div className="p-6 text-center text-muted-foreground">{error ?? "…"}</div>;
}
```

- [ ] **Step 3: Register routes**

In `frontend/src/App.tsx` add inside `<Routes>`:
```tsx
import Classes from "@/pages/Classes";
import JoinByLink from "@/pages/JoinByLink";
// ...
<Route
  path="/clases"
  element={
    <RequireAuth>
      <Shell>
        <Classes />
      </Shell>
    </RequireAuth>
  }
/>
<Route
  path="/join/:code"
  element={
    <RequireAuth>
      <JoinByLink />
    </RequireAuth>
  }
/>
```

- [ ] **Step 4: Verify and commit**

Manual (390 px, teacher account): create a class with a Mon 10:00–11:00 block → card shows code; copy link; open link in a second (student) session → auto-joins and lands on `/clases`. `npm run build` passes.

```bash
git add frontend/ && git commit -m "feat(frontend): classes page — create, join by code, invite links"
```

---

### Task 12: Production serving, Railway config, CI

**Files:**
- Modify: `backend/app/main.py`
- Create: `railway.json`, `nixpacks.toml`, `.github/workflows/ci.yml`
- Test: `backend/tests/test_static.py`

**Interfaces:**
- Consumes: the whole app.
- Produces: FastAPI serves `frontend/dist` with SPA fallback; Railway build/start commands; CI running pytest against PostgreSQL + frontend build.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_static.py`:
```python
def test_api_404_stays_json(client):
    res = client.get("/api/definitely-not-a-route")
    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/json")
```

Run: `pytest tests/test_static.py -v` — Expected: PASS already (FastAPI default). This test guards the SPA fallback we add next: it must never swallow `/api/*` 404s.

- [ ] **Step 2: Add SPA static serving**

Append to `backend/app/main.py`:
```python
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            # let FastAPI's 404 handling apply — this route only catches non-API paths
            from fastapi import HTTPException

            raise HTTPException(status_code=404)
        file = FRONTEND_DIST / full_path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(FRONTEND_DIST / "index.html")
```

Run: `pytest -v` — Expected: all pass (dist doesn't exist in tests, mount is skipped; the guard test still passes).

- [ ] **Step 3: Railway config**

`railway.json`:
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "cd frontend && npm ci && npm run build && cd ../backend && pip install -r requirements.txt"
  },
  "deploy": {
    "startCommand": "cd backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/api/health"
  }
}
```

`nixpacks.toml`:
```toml
providers = ["python", "node"]

[variables]
NIXPACKS_PYTHON_VERSION = "3.12"
```

Railway env vars to set in the dashboard (document in README): `DATABASE_URL` (auto from the Postgres plugin), `GOOGLE_CLIENT_ID`, `TEACHER_EMAIL`, `CORS_ORIGINS=https://<railway-domain>`.

- [ ] **Step 4: CI workflow**

`.github/workflows/ci.yml`:
```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready --health-interval 5s
          --health-timeout 5s --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r backend/requirements.txt
      - run: pytest backend/tests -v
        working-directory: backend
        env:
          TEST_DATABASE_URL: postgresql+psycopg://postgres:test@localhost:5432/test

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
      - run: npm ci
        working-directory: frontend
      - run: npm run build
        working-directory: frontend
```
Note the backend job runs pytest from the `backend/` working directory (conftest expects that), against real PostgreSQL.

- [ ] **Step 5: Verify, deploy, commit**

Local: `cd frontend && npm run build`, then `cd ../backend && uvicorn app.main:app` → http://localhost:8000 serves the app end to end (login → onboarding → clases).

Deploy: create the Railway project + Postgres plugin, connect the GitHub repo, set env vars, add the Railway domain to Google OAuth authorized origins. Verify `/api/health` and a real login on the Railway URL **from a phone**.

```bash
git add backend/ railway.json nixpacks.toml .github/
git commit -m "feat: production static serving, Railway config, CI with PostgreSQL"
git push origin main
```

---

### Task 13: Seed script, docs, phase close

**Files:**
- Create: `backend/seed.py`
- Modify: `README.md`, `planning/roadmap.md`, `planning/changelog.md`

**Interfaces:**
- Consumes: everything.
- Produces: `python seed.py` populates a local dev DB.

- [ ] **Step 1: Write the seed script**

`backend/seed.py`:
```python
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
```

Run: `cd backend && python seed.py` on a fresh DB (`rm school_v2.db && alembic upgrade head` first).
Expected: prints the class code; `/api/classes/mine` for the seeded teacher shows the class. (Note: seeded users have no real Google session — verify via DB or by temporarily creating a session row.)

- [ ] **Step 2: Update docs**

- `README.md`: replace the placeholder with dev setup (backend venv + `alembic upgrade head` + uvicorn; frontend `npm install` + `npm run dev`; seed script; Railway env vars list).
- `planning/roadmap.md`: check off completed Phase 0 items.
- `planning/changelog.md`: add a dated entry — Fase 0 completada, what shipped, Railway URL.

- [ ] **Step 3: Full verification pass**

Run: `cd backend && pytest -v` — all pass.
Run: `cd frontend && npm run build` — clean.
Manual on phone (or 390 px): login → onboarding → create class → copy invite link → join from second account → both see the class in `/clases`.

- [ ] **Step 4: Commit**

```bash
git add backend/seed.py README.md planning/
git commit -m "feat: seed script and Phase 0 close-out docs"
git push origin main
```

---

## Self-Review Notes

- **Spec coverage (Phase 0 scope only):** monorepo ✅ (T1, T7) · Alembic ✅ (T2, T5) · Google auth ✅ (T3, T8) · onboarding username/bio ✅ (T4, T9) · classes with schedule/dates/weights + join code + invite link ✅ (T5, T6, T11) · Railway deploy + FastAPI serves dist ✅ (T12) · CI on PostgreSQL ✅ (T12) · strings file with draft copy ✅ (T7) · mobile-first QA ✅ (manual steps at 390 px throughout). Feed, ledger, posts, attendance are later phases by design.
- **Type consistency:** `AuthResponse.needs_onboarding` used in T3 backend and T8 frontend; `ClassOut.schedule` maps from `schedule_json` via `validation_alias` (T6) and matches the frontend type (T7); fixtures `auth_headers`/`teacher_headers` defined T3, consumed T4/T6.
- **Known judgment calls:** shell UI in T10 is deliberately bare (emoji placeholders) — the real design pass happens with the feed in Phase 1 using the shadcn preset components; GIS button typing uses `any` (Google doesn't ship official types); frontend has no unit tests in Phase 0 (build + manual QA only) — vitest lands with the feed logic in Phase 1 where there's real logic to test.
