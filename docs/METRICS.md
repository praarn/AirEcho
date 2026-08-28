# Measured metrics

This file is **regenerated** by `python -m app.seed.seed` (and by
`app.ml.train.write_metrics_doc`) after models train against seeded data. Until
you run the seed it stays a placeholder.

Expected shape after a seeded run:

- **population fallback** (random_forest v1): MAE ~1.3–1.8 vs predict-the-mean ~1.9–2.3
- **user demo@example.com** (random_forest v1): MAE below the population model's,
  because the personal lag pattern in the synthetic data is user-specific

Other metrics to capture by hand for the write-up:

| Metric | How to get it |
|--------|---------------|
| Avg data coverage % across stations | `GET /exposure/coverage-summary` after seeding |
| Personalized vs population MAE per user | `GET /risk/models` |
| Minimum-data threshold + reasoning | `backend/app/ml/config.py` (`MIN_PERSONAL_SAMPLES`, `MIN_PERSONAL_DAYS`) |
| RAG citation-presence / correct-refusal rate | `python -m app.rag.eval` |
| OCR extraction accuracy | `pytest backend/tests/test_ocr.py -rP` against the labelled sample |
