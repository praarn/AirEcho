"""initial schema

Creates the pgvector extension, then materializes every table from the ORM
metadata (schema is single-sourced from app/models.py), then adds an IVFFlat
index on the guideline embedding for cosine search.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-28
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from app import models  # noqa: F401
from app.database import Base

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    Base.metadata.create_all(bind=bind)

    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_guideline_chunks_embedding "
            "ON guideline_chunks USING ivfflat (embedding vector_cosine_ops) "
            "WITH (lists = 10)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_guideline_chunks_embedding")
    Base.metadata.drop_all(bind=bind)
