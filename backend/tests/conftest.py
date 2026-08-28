"""Test harness.

Runs against a throwaway SQLite file so the suite needs no Postgres service
(CI *also* runs it against real Postgres + pgvector via ci.yml). The
`EmbeddingType` column degrades to JSON text on SQLite and retrieval falls back
to NumPy cosine, so the RAG tests still exercise the real ranking logic.
"""

from __future__ import annotations

import os
import pathlib

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./_test_aq.db")
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-0123456789")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("SYNTHETIC_INGEST", "false")
os.environ.setdefault("LLM_API_KEY", "")

_db_file = pathlib.Path("./_test_aq.db")
if _db_file.exists():
    _db_file.unlink()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _register_login(c: TestClient, email: str) -> dict:
    c.post("/auth/register", json={"email": email, "password": "pw-abcdefgh"})
    r = c.post("/auth/login", json={"email": email, "password": "pw-abcdefgh"})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def auth(client):
    tokens = _register_login(client, "a@example.com")
    client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})
    return tokens


@pytest.fixture
def user_a(client):
    return _register_login(client, "user-a@example.com")


@pytest.fixture
def user_b(client):
    return _register_login(client, "user-b@example.com")
