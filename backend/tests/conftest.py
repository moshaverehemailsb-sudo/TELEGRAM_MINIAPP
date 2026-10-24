"""Test setup. Runs against a SEPARATE database. Tables are dropped and recreated here."""

import os

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL", "")
if not TEST_DB or "test" not in TEST_DB.lower():
    raise RuntimeError(
        "TEST_DATABASE_URL must point to a separate test database whose name contains 'test'. "
        "Never use the real database here."
    )

# These must be set BEFORE the app is imported, so the settings pick them up.
os.environ["DATABASE_URL"] = TEST_DB
os.environ["APP_ENV"] = "development"
os.environ["ALLOW_DEV_AUTH"] = "true"
os.environ["ADMIN_TELEGRAM_IDS"] = "1000"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Subject  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def clean_db():
    tables = ", ".join(Base.metadata.tables.keys())
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    with SessionLocal() as db:
        db.add_all([
            Subject(code="math", name_fa="ریاضی", sort_order=1),
            Subject(code="physics", name_fa="فیزیک", sort_order=2),
            Subject(code="chemistry", name_fa="شیمی", sort_order=3),
        ])
        db.commit()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session