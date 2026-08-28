"""Grounded advisory generation.

Hard rules (health-adjacent content — these matter more here than elsewhere):
  * The response may only rephrase/contextualize RETRIEVED text.
  * Every response carries inline [n] citations resolving to a guideline section.
  * If the best retrieval similarity < settings.rag_min_score, we REFUSE with an
    explicit "the available guidelines don't specifically address this" — the LLM
    is never asked to improvise.
  * Post-generation guard: any numeric token in the response that does not appear
    in a retrieved chunk causes us to discard the LLM text and fall back to the
    deterministic template renderer (which only ever emits grounded numbers).

`call_llm` is the single seam unit tests monkeypatch.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AdvisoryLog
from app.rag.retrieve import RetrievedChunk, retrieve

REFUSAL_TEXT = (
    "The available WHO and CPCB guidelines indexed here don't specifically address "
    "this situation, so I can't give a grounded answer. Nothing in the retrieved "
    "passages covers it closely enough to cite. Consider consulting a clinician or "
    "the full guideline documents directly."
)

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def _numbers(text: str) -> set[str]:
    return set(_NUM_RE.findall(text))


def call_llm(system: str, user: str) -> str:
    """OpenAI-compatible chat completion. Returns '' when unconfigured so the
    caller uses the deterministic renderer. Never raises into the request path."""
    if not settings.llm_api_key:
        return ""
    try:
        resp = httpx.post(
            f"{settings.llm_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={
                "model": settings.llm_model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, ValueError):
        return ""


def _template_answer(context_line: str, chunks: list[RetrievedChunk]) -> str:
    parts = [context_line.strip()] if context_line.strip() else []
    parts.append("Here is what the indexed guidelines say, quoted and cited:")
    for i, c in enumerate(chunks, start=1):
        parts.append(f"[{i}] {c.text}")
    parts.append(
        "These passages are the only basis for the statement above; anything not "
        "cited here is not established by the retrieved guidelines."
    )
    return "\n\n".join(parts)


def _build_context_line(context: dict) -> str:
    bits = []
    if context.get("pm25") is not None:
        bits.append(f"current PM2.5 ≈ {context['pm25']:.0f} µg/m³")
    if context.get("risk_score") is not None:
        label = "personalized" if context.get("is_personalized") else "population-fallback"
        bits.append(f"{label} risk score {context['risk_score']:.1f}/10")
    if context.get("data_coverage_pct") is not None:
        bits.append(f"exposure-window data coverage {context['data_coverage_pct']:.0f}%")
    return ("Your current context: " + "; ".join(bits) + ".") if bits else ""


def generate_advisory(
    db: Session,
    *,
    user_id: int,
    question: str | None,
    context: dict,
) -> dict:
    query = question or (
        "What do air quality guidelines say about my current pollution exposure "
        "and any precautions for someone with respiratory sensitivity?"
    )
    chunks = retrieve(db, query, top_k=settings.rag_top_k)
    top_sim = chunks[0].similarity if chunks else -1.0
    now = datetime.now(UTC)

    if not chunks or top_sim < settings.rag_min_score:
        log = AdvisoryLog(
            user_id=user_id,
            question_or_context=query,
            retrieved_chunks_json=[_chunk_dict(c) for c in chunks],
            response_text=REFUSAL_TEXT,
            citations_json=[],
            refused=True,
        )
        db.add(log)
        db.commit()
        return {
            "response_text": REFUSAL_TEXT,
            "citations": [],
            "refused": True,
            "context_used": context,
            "created_at": now,
        }

    context_line = _build_context_line(context)
    grounded_numbers = _numbers(" ".join(c.text for c in chunks)) | _numbers(context_line)

    system = (
        "You are a cautious health-information assistant. You may ONLY rephrase and "
        "contextualize the numbered guideline passages provided. Never state a number, "
        "threshold, limit, or health claim that is not present in those passages. Put an "
        "inline citation like [1] after every sentence that uses a passage. If the "
        "passages do not cover the question, say so."
    )
    user = f"{context_line}\n\nQuestion: {query}\n\nGuideline passages:\n" + "\n".join(
        f"[{i}] ({c.section_ref}) {c.text}" for i, c in enumerate(chunks, 1)
    )
    llm_text = call_llm(system, user)

    used_template = False
    # ignore the citation markers themselves ([1], [2] …) when checking numbers
    llm_numbers = _numbers(re.sub(r"\[\d+\]", " ", llm_text)) if llm_text else set()
    if not llm_text or not re.search(r"\[\d+\]", llm_text):
        llm_text, used_template = _template_answer(context_line, chunks), True
    elif llm_numbers - grounded_numbers:
        # LLM introduced a number we can't trace to a chunk → discard it
        llm_text, used_template = _template_answer(context_line, chunks), True

    # every retrieved passage is surfaced as a citation — the reader can see the
    # complete grounding, not just the markers the LLM chose to type.
    citations = [
        {
            "marker": f"[{i}]",
            "section_ref": c.section_ref,
            "document_title": c.document_title,
            "score": round(c.similarity, 4),
            "snippet": c.text[:240],
        }
        for i, c in enumerate(chunks, start=1)
    ]

    log = AdvisoryLog(
        user_id=user_id,
        question_or_context=query,
        retrieved_chunks_json=[_chunk_dict(c) for c in chunks],
        response_text=llm_text,
        citations_json=citations,
        refused=False,
    )
    db.add(log)
    db.commit()
    return {
        "response_text": llm_text,
        "citations": citations,
        "refused": False,
        "context_used": {**context, "used_template_renderer": used_template},
        "created_at": now,
    }


def _chunk_dict(c: RetrievedChunk) -> dict:
    return {
        "chunk_id": c.chunk_id,
        "section_ref": c.section_ref,
        "document_title": c.document_title,
        "similarity": round(c.similarity, 4),
    }
