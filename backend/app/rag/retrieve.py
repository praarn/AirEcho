"""Vector retrieval over `guideline_chunks`.

PostgreSQL: `pgvector` cosine distance, ordered in the DB.
SQLite (tests): load all chunk vectors, cosine in NumPy.
Both return `(chunk, similarity)` with similarity in [-1, 1], higher = closer.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import GuidelineChunk, GuidelineDocument
from app.rag.embed import embed_texts


@dataclass
class RetrievedChunk:
    chunk_id: int
    section_ref: str
    document_title: str
    text: str
    similarity: float


def retrieve(db: Session, query: str, *, top_k: int | None = None) -> list[RetrievedChunk]:
    top_k = top_k or settings.rag_top_k
    qvec = embed_texts([query])[0]

    if db.bind.dialect.name == "postgresql":
        rows = db.execute(
            select(
                GuidelineChunk,
                GuidelineDocument.title,
                GuidelineChunk.embedding.cosine_distance(qvec).label("dist"),
            )
            .join(GuidelineDocument, GuidelineDocument.id == GuidelineChunk.doc_id)
            .order_by("dist")
            .limit(top_k)
        ).all()
        return [
            RetrievedChunk(c.id, c.section_ref, title, c.chunk_text, float(1.0 - dist))
            for c, title, dist in rows
        ]

    # generic path
    rows = db.execute(
        select(GuidelineChunk, GuidelineDocument.title).join(
            GuidelineDocument, GuidelineDocument.id == GuidelineChunk.doc_id
        )
    ).all()
    if not rows:
        return []
    q = np.asarray(qvec, dtype=float)
    q /= np.linalg.norm(q) or 1.0
    scored: list[RetrievedChunk] = []
    for c, title in rows:
        if not c.embedding:
            continue
        v = np.asarray(c.embedding, dtype=float)
        v /= np.linalg.norm(v) or 1.0
        scored.append(RetrievedChunk(c.id, c.section_ref, title, c.chunk_text, float(np.dot(q, v))))
    scored.sort(key=lambda r: r.similarity, reverse=True)
    return scored[:top_k]
