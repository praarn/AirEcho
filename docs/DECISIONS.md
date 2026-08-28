# Design decisions & where I simplified

Written to be read alongside the code. The brief asked for a rationale on
non-obvious choices and an honest list of simplifications — this is that.

## Non-obvious decisions

### Why a time-based split matters here
Symptom severity is a time series with autocorrelation and slow pollution
episodes lasting days. A random split puts rows from the *same episode* in both
train and test, so the model gets credit for interpolating within an episode it
already saw. That inflates the score and hides the fact that the model can't
extrapolate to a *new* episode — which is the only thing that matters for a
"what will tomorrow feel like" prediction. `time_based_split` sorts by
`logged_at` and cuts; `tests/test_risk_model.py` asserts
`max(train.logged_at) <= min(test.logged_at)`.

### How the minimum-data threshold was chosen (`MIN_PERSONAL_SAMPLES=30`, `MIN_PERSONAL_DAYS=14`)
Two independent bars, both required:
- **30 feature-complete logs** — with a 25 %/75 % time split that leaves a test
  fold of ~7, the smallest fold where MAE isn't dominated by one or two points,
  and enough for a shallow RandomForest to see each lag×pollutant combination
  more than once.
- **14 days of span** — 30 logs from a single week describe *one* pollution
  episode. Two weeks is the minimum window that can plausibly contain both a
  high and a low exposure regime, which is what makes a lag coefficient
  identifiable rather than a fit to one spike.

Below either bar the API serves the population fallback, labelled in the UI as
"general pattern, not yet personalized to you" — never dressed up as personal.

### Why the RAG layer refuses instead of guessing
This is health-adjacent. An LLM confidently stating "keep PM2.5 under X" when X
isn't in a retrieved WHO/CPCB passage is worse than saying nothing. So:
`rag_min_score` gates on cosine similarity of the top chunk; below it we return a
fixed refusal. Above it, the LLM is constrained to rephrase retrieved text, and a
post-generation check strips any numeric token not present in a retrieved chunk
(falling back to a deterministic renderer that only emits grounded numbers).
Every response carries the full retrieved set as inline citations.

### Why `data_coverage_pct` is a stored column and a model feature, not just a log line
If coverage only lived in logs, every downstream consumer would silently treat a
40 %-covered 24h average the same as a 100 %-covered one. Storing it on the row
means the API, the dashboard, and the model all see it. As a **feature**
(`coverage_lag*`), the model can learn to discount a lag window when the sensor
was quiet, instead of us hard-coding an imputation rule.

### Why sync SQLAlchemy
Nothing here needs async DB access. The scheduler does its DB work in a
threadpool; WebSocket broadcasts don't touch the ORM on the hot path. Sync keeps
Alembic, tests (`TestClient`), and the mental model simple.

## Simplifications (deliberate, documented, not hidden)

| Area | Simplification | Why it's acceptable |
|------|----------------|---------------------|
| OCR | Tesseract digit-reading only, `--psm 7` whitelist `0-9`. Vision-LLM fallback is a stub. | The brief calls for digit extraction with a confirm-or-correct gate, not a vision model. Low-confidence reads are never trusted. |
| Ingestion | `SYNTHETIC_INGEST=true` generates gappy readings when OpenAQ isn't reachable. OpenAQ v3 path is best-effort. | Keeps a fresh clone demoable offline; the gap/coverage logic is identical for synthetic and real data. |
| Guideline corpus | Bundled as short faithful paraphrases in `app/rag/guidelines_data.py`, not the full PDFs. | Offline-indexable; swap in verbatim passages + keep the `section_ref` citations for production. |
| Weather | Daily synthetic temp/humidity/rainfall; joined into windows by station location name. | Weather is a context feature here, not a headline output. |
| Embeddings on SQLite | `EmbeddingType` degrades to JSON text and retrieval falls back to NumPy cosine, so the test suite runs without Postgres. | CI *also* runs the suite against real Postgres + `pgvector`; production is always `pgvector`. |
| Population model | Pools every user's feature rows, drops `user_id` before the frame is returned, splits by time. No k-anon / DP beyond identifier stripping. | Matches the brief ("anonymized/aggregated, no user_id joined into training"); a test asserts the column is absent. |
| Auth | JWT in `localStorage` on the client (not httpOnly cookies). | Simplicity for a portfolio SPA; refresh tokens are hashed at rest and rotated with reuse-detection server-side. |
| Scheduler | Single in-process `asyncio` loop; no leader election. | Explicitly required by the brief (no Celery/Redis). Fine for one backend replica. |

## Assumptions

- One "primary" location per user drives the model (first location with a
  resolved station). Multi-location modeling is out of scope.
- Symptom `logged_at` is trustworthy as the alignment anchor.
- Station `nominal_cadence_minutes` is a good enough denominator for expected
  slots; a station that reports irregularly *by design* would need a learned
  cadence.
