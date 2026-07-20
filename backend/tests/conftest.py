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
