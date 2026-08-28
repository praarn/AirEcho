# AirEcho

**Air-Quality Health Risk Correlator** — today's air echoes into how you feel tomorrow.

Generic AQI apps show the same number to everyone. AirEcho ties **a person's own
exposure history to their own symptom pattern**, with the modeling done honestly
(**lagged** features at t-0 / t-6h / t-24h, not same-day correlation) and the advisory
text **grounded in cited WHO / CPCB guideline passages** rather than an LLM improvising
thresholds.

The hard engineering problem is **aligning three genuinely irregular time series** —
sensor readings on their own polling cadence, weather on another, and user-logged
symptoms logged whenever the user happens to log them — into one feature space a model
can learn from, **without ever pretending the data is cleaner or more complete than it
is**.

> **Honest scoping note (read this).** Self-reported symptom severity correlated with
> lagged pollutant exposure is exactly that: *correlational*, small-sample, and noisy.
> This is **not causal inference**. Nothing in the UI or the API claims otherwise. The
> value of the project is the honesty of the pipeline — explicit data-coverage
> accounting, time-based splits, a population fallback for thin-history users, and a RAG
> layer that refuses rather than guesses.

---

## Architecture

```
┌─────────────┐     JWT (access + rotating refresh)      ┌──────────────────────┐
│  Next.js 15 │  ──────────────────────────────────────► │  FastAPI (Python)    │
│  Tailwind   │  ◄────────  REST + WebSocket  ─────────── │  Pydantic v2         │
└─────────────┘                                           └─────────┬────────────┘
                                                                    │ SQLAlchemy 2.0
                                                          ┌─────────▼────────────┐
                                                          │ PostgreSQL + pgvector │
                                                          └──────────────────────┘

Background asyncio scheduler (in-process, no Celery / Redis):
  ingest AQI + weather  →  log gaps  →  materialize exposure_windows  →  retrain models
```

| Layer        | Choice                                                                    |
|--------------|--------------------------------------------------------------------------|
| Frontend     | Next.js 15 (App Router), TypeScript, Tailwind CSS, Recharts             |
| Backend      | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (sync), Alembic       |
| Database     | PostgreSQL 16 + `pgvector` (RAG embeddings live in the same instance)   |
| ML / Data    | Pandas, NumPy, scikit-learn (lagged `LinearRegression` → `RandomForestRegressor`) |
| RAG          | `sentence-transformers` (`all-MiniLM-L6-v2`) + `pgvector` cosine search |
| OCR          | Tesseract (`pytesseract`), vision-LLM documented fallback              |
| Auth         | JWT access (short-lived) + refresh tokens rotated on every use          |
| Infra        | Docker + Docker Compose only                                            |
| CI           | GitHub Actions (lint → pytest against real Postgres+pgvector → FE build)|
| Tests        | Pytest + FastAPI `TestClient`                                           |

---

## Quick start

```bash
cp .env.example .env          # fill LLM_API_KEY if you want live advisory text
docker compose up --build     # postgres + backend + frontend

# in another shell, once containers are healthy:
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed.seed      # synthetic gappy data + guidelines
```

- Frontend: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>
- Seeded demo login: `demo@example.com` / `demo-pass-123` (rich history, personal model)
- Seeded thin login: `new@example.com` / `demo-pass-123` (population fallback only)

### Run the backend without Docker

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate      # Windows
pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://aq:aq@localhost:5432/aq
alembic upgrade head
uvicorn app.main:app --reload
pytest -q
```

---

## The two core deliverables

### 1. Exposure-window pipeline — honest about irregular time series

`app/services/exposure_pipeline.py` materializes `exposure_windows` (6h / 24h / 72h) per
user-location from raw `aqi_readings`. Every window stores **`data_coverage_pct`**:

```
data_coverage_pct = observed_slots / expected_slots
expected_slots    = window_length / nominal_station_cadence
```

A rolling average is **never** computed as if a gap didn't exist — a window that only saw
40 % of its expected readings is stored with `data_coverage_pct = 40.0`, and that number
is surfaced all the way to the dashboard (a gappy period visibly looks gappy). Tests in
`tests/test_exposure_windows.py` build synthetic readings with deliberate holes and
assert both the averages and the coverage percentages against hand-computed values.

### 2. Lagged risk modeling — not a black box

`app/ml/` constructs features at **t-0, t-6h, t-24h, t-72h** for each pollutant plus
weather, then:

- **Baseline:** lagged `LinearRegression` (interpretable coefficients).
- **Primary per-user model:** `RandomForestRegressor`, used only once the user clears the
  **minimum-data threshold** (`MIN_PERSONAL_SAMPLES = 30` aligned symptom logs spanning
  `MIN_PERSONAL_DAYS = 14` days — see `app/ml/config.py` for the reasoning).
- **Population fallback:** trained on **anonymized aggregated** exposure/symptom pairs
  with `user_id` stripped *before* the frame reaches the trainer. Labeled everywhere in
  the UI as *"general pattern, not yet personalized to you."*
- **Evaluation:** strict **time-based** train/test split — `tests/test_risk_model.py`
  asserts no `logged_at` in the test set precedes any `logged_at` in the training set.
  MAE reported for both personal and fallback models; feature importances exposed via
  `GET /risk/explain`.

---

## Grounded RAG advisory

`app/rag/` chunks and embeds the bundled WHO Global Air Quality Guidelines (2021) and
CPCB National Air Quality Index summaries, stores vectors in `pgvector`, and generates
advisory text that **only rephrases retrieved passages**. Every response carries inline
`[1]`, `[2]` citations resolving to `guideline_chunks.section_ref`. When the top
retrieval score is below `RAG_MIN_SCORE`, the system returns an explicit
*"the available guidelines don't specifically address this"* refusal instead of letting
the LLM improvise. `tests/test_rag.py` mocks the LLM and asserts citation presence plus
correct refusal on out-of-corpus questions.

---

## Privacy

- Per-user isolation is enforced **in the query layer** (`scoped_query()` in
  `app/api/deps.py` injects `WHERE user_id = :current_user`), never trusted from request
  params. `tests/test_isolation.py` asserts user A gets `404` on every one of user B's
  resources.
- `GET /privacy/export` returns a full JSON dump of the caller's health data.
- `DELETE /privacy/delete` hard-deletes it and revokes all refresh tokens.
- Population training calls `aggregate_training_frame()` which drops `user_id` before the
  DataFrame is returned; a test asserts the column is absent.

---

## Metrics captured (see `docs/METRICS.md` after a seeded run)

| Metric | Where |
|--------|-------|
| Avg data coverage % across stations | `GET /exposure/coverage-summary` |
| Personal vs population-fallback MAE | `risk_models.mae`, shown on dashboard |
| Minimum-data threshold + reasoning | `app/ml/config.py` |
| RAG citation-presence / correct-refusal rate | `python -m app.rag.eval` |
| OCR accuracy on the labelled sample | `pytest tests/test_ocr.py -rP` |

---

## Repository layout

```
backend/
  app/
    api/routes/       auth, locations, ingestion, exposure, symptoms, risk, advisory, privacy, ws
    core/security.py  JWT mint/verify, password hashing, refresh rotation
    services/         ingestion, exposure_pipeline, ocr, scheduler
    ml/               features, train, predict, config (thresholds + rationale)
    rag/              embed, retrieve, advisory, eval
    seed/             seed.py + bundled guideline text
  tests/              the gap-handling and lag-feature suites are the centerpieces
frontend/
  app/                landing, login, register, dashboard
  components/         AqiGauge, RiskCard, ExposureTrendChart, SymptomTimeline,
                      CoverageBadge, WhyThisScore, AdvisoryPanel, LiveAlertsFeed
docs/                 the original brief + generated METRICS.md
```
