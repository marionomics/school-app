import os
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.sessions import create_session
from app.database import Base, get_db
from app.main import app
from app.models import Class, Enrollment, User

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


@pytest.fixture()
def klass(db, teacher):
    k = Class(
        name="Micro", code="MICRO2026TEST", teacher_id=teacher.id,
        start_date=date(2026, 8, 17), end_date=date(2026, 12, 4),
        schedule_json=[{"day": 0, "start": "10:00", "end": "11:00"}],
    )
    db.add(k)
    db.commit()
    db.refresh(k)
    return k


@pytest.fixture()
def enrolled(db, student, klass):
    e = Enrollment(user_id=student.id, class_id=klass.id)
    db.add(e)
    db.commit()
    return e


@pytest.fixture()
def student2(db, klass):
    u = User(google_id="g-student2", email="alumno2@example.com", name="Alumno Dos")
    db.add(u)
    db.commit()
    db.add(Enrollment(user_id=u.id, class_id=klass.id))
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def student2_headers(db, student2):
    return {"Authorization": f"Bearer {create_session(db, student2)}"}


@pytest.fixture()
def ghost(db, klass):
    u = User(google_id="g-ghost", email="ghost@example.com", name="Fantasma")
    db.add(u)
    db.commit()
    db.add(Enrollment(user_id=u.id, class_id=klass.id, status="ghost"))
    db.commit()
    db.refresh(u)
    return u
