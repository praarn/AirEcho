"""Engine / session wiring. Sync SQLAlchemy 2.0 — simpler to test with
`TestClient`, and nothing in this app needs async DB access (the scheduler runs
its DB work in a threadpool)."""

from __future__ import annotations

import json
from collections.abc import Iterator

from sqlalchemy import Float, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.config import settings

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


class EmbeddingType(TypeDecorator):
    """Real `pgvector.Vector` on PostgreSQL; JSON-encoded float list on SQLite so
    the test suite can run without a Postgres service. Retrieval code picks the
    matching similarity path per dialect."""

    impl = Text
    cache_ok = True

    def __init__(self, dim: int):
        self.dim = dim
        super().__init__()

    class Comparator(TypeDecorator.Comparator):
        """`TypeDecorator` does not forward the wrapped type's comparator, so
        pgvector's distance operators have to be re-declared here to be usable as
        `GuidelineChunk.embedding.cosine_distance(vec)` on PostgreSQL."""

        def cosine_distance(self, other):
            return self.op("<=>", return_type=Float)(other)

        def l2_distance(self, other):
            return self.op("<->", return_type=Float)(other)

        def max_inner_product(self, other):
            return self.op("<#>", return_type=Float)(other)

    comparator_factory = Comparator

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return list(value)
        return json.dumps([float(x) for x in value])

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return list(value)
        return json.loads(value)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
