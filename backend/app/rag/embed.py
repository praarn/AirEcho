"""Embedding + indexing. `sentence-transformers` (all-MiniLM-L6-v2, 384-dim),
vectors stored in the same Postgres instance via `pgvector`.

The model is loaded lazily and cached process-wide. Unit tests monkeypatch
`embed_texts` so they never download weights.
"""

from __future__ import annotations

import functools

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import GuidelineChunk, GuidelineDocument
from app.rag.guidelines_data import GUIDELINES


@functools.lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    vecs = _model().encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return [v.tolist() for v in vecs]


def chunk_section(section_ref: str, text: str, *, max_chars: int = 700) -> list[tuple[str, str]]:
    """Guideline sections are already short; split only if a section runs long,
    keeping the section_ref (with a part suffix) so citations stay precise."""
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return [(section_ref, text)]
    out, buf = [], ""
    for sentence in text.replace("? ", "?\n").replace(". ", ".\n").split("\n"):
        if len(buf) + len(sentence) > max_chars and buf:
            out.append(buf.strip())
            buf = ""
        buf += sentence + " "
    if buf.strip():
        out.append(buf.strip())
    return [(f"{section_ref} (part {i + 1})", c) for i, c in enumerate(out)]


def index_guidelines(db: Session, *, reset: bool = True) -> dict:
    """Idempotent: (re)builds `guideline_documents` + `guideline_chunks` with
    embeddings from the bundled corpus."""
    if reset:
        db.query(GuidelineChunk).delete()
        db.query(GuidelineDocument).delete()
        db.flush()

    pending: list[tuple[int, str, str]] = []
    for doc in GUIDELINES:
        d = GuidelineDocument(
            title=doc["title"], source_url=doc.get("source_url"), publisher=doc["publisher"]
        )
        db.add(d)
        db.flush()
        for section_ref, text in doc["sections"]:
            for ref, chunk in chunk_section(section_ref, text):
                pending.append((d.id, ref, chunk))

    vectors = embed_texts([c for _, _, c in pending])
    for (doc_id, ref, chunk), vec in zip(pending, vectors, strict=True):
        db.add(GuidelineChunk(doc_id=doc_id, section_ref=ref, chunk_text=chunk, embedding=vec))
    db.commit()

    n_docs = db.execute(select(GuidelineDocument)).scalars().all()
    return {"documents": len(n_docs), "chunks": len(pending)}
