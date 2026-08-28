"""Tiny hand-written eval set for the RAG layer.

Run: `python -m app.rag.eval`  (needs a migrated DB with guidelines indexed)

Reports citation-presence rate (grounded questions that came back with >=1
citation) and correct-refusal rate (out-of-corpus questions that were refused).
"""

from __future__ import annotations

import json

from app.database import SessionLocal
from app.rag.advisory import generate_advisory

GROUNDED = [
    ("What is the WHO 24-hour guideline for PM2.5?", "PM2.5"),
    ("What does WHO recommend for annual NO2 exposure?", "NO2"),
    ("Which groups are most at risk from air pollution?", "at higher risk"),
    ("What are the CPCB air quality index categories?", "Categories"),
    ("What does ozone exposure do to the lungs?", "Ozone"),
]

OUT_OF_CORPUS = [
    "Should I take vitamin D supplements for my asthma?",
    "What brand of air purifier filter lasts longest?",
    "Is it safe to fly with a chest infection next week?",
]


def run() -> dict:
    db = SessionLocal()
    try:
        cited = 0
        for q, _ in GROUNDED:
            out = generate_advisory(db, user_id=0, question=q, context={})
            if not out["refused"] and out["citations"]:
                cited += 1
        refused = 0
        for q in OUT_OF_CORPUS:
            out = generate_advisory(db, user_id=0, question=q, context={})
            if out["refused"]:
                refused += 1
        report = {
            "citation_presence_rate": round(cited / len(GROUNDED), 3),
            "correct_refusal_rate": round(refused / len(OUT_OF_CORPUS), 3),
            "n_grounded": len(GROUNDED),
            "n_out_of_corpus": len(OUT_OF_CORPUS),
        }
        print(json.dumps(report, indent=2))
        return report
    finally:
        db.close()


if __name__ == "__main__":
    run()
