"""Grounded RAG advisory tests.

The embedding model and the LLM are both mocked — no weights downloaded, no
network. What's under test is the pipeline contract:
  * every non-refused advisory carries >=1 citation
  * out-of-corpus questions are refused, not improvised
  * an LLM answer containing an untraceable number is discarded for the
    deterministic (grounded-only) renderer
"""

from __future__ import annotations

import hashlib
import math
import re

import pytest

import app.rag.advisory as advisory_mod
import app.rag.embed as embed_mod
import app.rag.retrieve as retrieve_mod

_DIM = 96
_STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "is",
    "are",
    "be",
    "what",
    "does",
    "do",
    "say",
    "about",
    "my",
    "i",
    "should",
    "how",
    "much",
    "this",
    "that",
    "with",
    "per",
    "help",
    "at",
    "it",
    "can",
    "you",
}


def _fake_embed(texts: list[str]) -> list[list[float]]:
    """Deterministic hashing bag-of-words → L2-normalized vector. On-topic text
    shares enough tokens with the guideline chunks to clear the similarity
    floor; unrelated text does not."""
    out = []
    for t in texts:
        vec = [0.0] * _DIM
        for tok in re.findall(r"[a-z0-9.]+", t.lower()):
            if tok in _STOP or len(tok) < 2:
                continue
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            vec[h % _DIM] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        out.append([v / norm for v in vec])
    return out


@pytest.fixture
def indexed(db, monkeypatch):
    monkeypatch.setattr(embed_mod, "embed_texts", _fake_embed)
    monkeypatch.setattr(retrieve_mod, "embed_texts", _fake_embed)
    from app.rag.embed import index_guidelines

    stats = index_guidelines(db, reset=True)
    assert stats["chunks"] > 0
    return db


def test_grounded_question_has_citations(indexed, monkeypatch):
    monkeypatch.setattr(advisory_mod, "call_llm", lambda *a, **k: "")  # force template renderer
    out = advisory_mod.generate_advisory(
        indexed,
        user_id=1,
        question="What does the WHO guideline recommend for PM2.5 particulate matter exposure?",
        context={"pm25": 55.0, "risk_score": 6.1, "is_personalized": False},
    )
    assert out["refused"] is False
    assert len(out["citations"]) >= 1
    assert any("PM2.5" in c["section_ref"] or "PM2.5" in c["snippet"] for c in out["citations"])
    assert "[1]" in out["response_text"]


def test_out_of_corpus_question_is_refused(indexed):
    out = advisory_mod.generate_advisory(
        indexed,
        user_id=1,
        question="What is the best recipe for a chocolate birthday cake?",
        context={},
    )
    assert out["refused"] is True
    assert out["citations"] == []
    assert "don't specifically address" in out["response_text"]


def test_refusal_is_logged(indexed):
    from app.models import AdvisoryLog

    advisory_mod.generate_advisory(
        indexed,
        user_id=7,
        question="How many concert tickets can I buy before Saturday evening?",
        context={},
    )
    row = indexed.query(AdvisoryLog).filter(AdvisoryLog.user_id == 7).one()
    assert row.refused is True


def test_llm_number_not_in_corpus_is_stripped(indexed, monkeypatch):
    # LLM tries to assert a threshold (999) that no retrieved chunk contains
    monkeypatch.setattr(
        advisory_mod,
        "call_llm",
        lambda *a, **k: "You should keep PM2.5 particulate under 999 at all times [1].",
    )
    out = advisory_mod.generate_advisory(
        indexed,
        user_id=1,
        question="What does the WHO guideline recommend for PM2.5 particulate matter?",
        context={},
    )
    assert out["refused"] is False
    assert "999" not in out["response_text"]  # ungrounded number discarded
    assert out["context_used"]["used_template_renderer"] is True
    assert len(out["citations"]) >= 1


def test_llm_answer_with_grounded_numbers_is_kept(indexed, monkeypatch):
    monkeypatch.setattr(
        advisory_mod,
        "call_llm",
        lambda *a, **k: "WHO recommends a 24-hour PM2.5 particulate mean not exceeding 15 [1].",
    )
    out = advisory_mod.generate_advisory(
        indexed,
        user_id=1,
        question="What is the WHO 24-hour PM2.5 particulate matter guideline value?",
        context={},
    )
    assert out["refused"] is False
    assert "15" in out["response_text"]
    assert out["context_used"].get("used_template_renderer") is False
