# explanation.md — project root

Plain-language walkthrough of **AirEcho**: what it is, how the pieces connect, and
how to run it. Every subdirectory that holds real logic has its own
`explanation.md` going one level deeper; this file is the map.

---

## What the project actually does

A person logs their respiratory symptoms (a 0–10 severity, optionally a peak-flow
meter photo). In the background the app pulls air-quality readings for a station
near that person and daily weather. It then:

1. **Aligns three irregular time series** — sensor readings, weather, and symptom
   logs — into fixed *exposure windows* (6h / 24h / 72h), and records how complete
   each window's data actually was (`data_coverage_pct`).
2. **Builds lagged features** — pollutant exposure at t-0, t-6h, t-24h, t-72h
   before each symptom — and trains a model to predict symptom severity from the
   *past*, not from same-day co-occurrence.
3. **Serves a personal model** once the user has enough history (30+ aligned logs
   over 14+ days), otherwise a clearly-labelled **population fallback** trained on
   anonymized pooled data.
4. **Generates advisory text** that only rephrases retrieved WHO / CPCB guideline
   passages, with inline citations, and refuses when the guidelines don't cover
   the question.

The guiding principle throughout: **never make the data look cleaner or more
certain than it is.** Coverage percentages, time-based evaluation, the
population-fallback label, and the RAG refusal path are all expressions of that.

> It models *correlation* between self-reported severity and lagged exposure in a
> small, noisy sample. It is not causal inference and the UI never claims it is.

---

## Directory map

```
air-quality/
├── explanation.md            ← you are here
├── README.md                 project pitch + architecture (author-written)
├── IMPLEMENTATION.md          long-form implementation notes (author-written)
├── COMMANDS.md                every run/seed/test command, PowerShell-first
├── docker-compose.yml         db (postgres+pgvector) + backend + frontend
├── .env / .env.example        configuration (see "Configuration" below)
│
├── backend/                   FastAPI + SQLAlchemy + scikit-learn + RAG
│   ├── explanation.md         backend overview & request lifecycle
│   ├── app/
│   │   ├── api/               ← explanation.md — routes, auth deps, WebSocket
│   │   ├── services/          ← explanation.md — ingestion, exposure pipeline, scheduler, OCR, geo
│   │   ├── ml/                ← explanation.md — lag features, training, prediction, thresholds
│   │   ├── rag/               ← explanation.md — embed, retrieve, grounded advisory, eval
│   │   ├── seed/              ← explanation.md — one-command demo dataset
│   │   ├── models.py          ORM tables
│   │   ├── schemas.py         Pydantic v2 request/response models
│   │   ├── config.py          pydantic-settings, env-driven
│   │   ├── database.py        engine/session + the pgvector⇄SQLite embedding shim
│   │   └── main.py            app assembly, CORS, lifespan → scheduler
│   ├── alembic/               ← explanation.md — schema migrations
│   └── tests/                 ← explanation.md — pytest suite (SQLite, 47 tests)
│
└── frontend/                  Next.js 15 App Router + Tailwind + Recharts
    ├── explanation.md         frontend overview
    ├── app/                   ← explanation.md — routes/pages
    ├── components/            ← explanation.md — dashboard widgets
    └── lib/                   ← explanation.md — API client, auth context, formatting
```

---

## How a request flows end to end

```
Browser (Next.js)
  │  fetch("/api/risk/score")           lib/api.ts adds the bearer token,
  │                                     auto-refreshes on 401
  ▼
Next.js dev server / container
  │  rewrites /api/* → http://backend:8000/*   (next.config.mjs)
  ▼
FastAPI (backend/app/main.py)
  │  router = risk.py → deps.current_user decodes JWT → deps.scoped()
  │  constrains every query to WHERE user_id = <caller>
  ▼
app/ml/predict.py
  │  pick active model (personal RF → population RF → heuristic)
  │  build the current lag-feature row from app/ml/features.py
  │  which calls app/services/exposure_pipeline.compute_exposure_window()
  ▼
PostgreSQL + pgvector   (aqi_readings, exposure_windows, risk_models, guideline_chunks …)
```

A **background asyncio task** (`app/services/scheduler.py`), started from the
FastAPI lifespan, runs the other direction every `INGEST_INTERVAL_MINUTES`:
`ingest synthetic/OpenAQ readings → materialize exposure_windows → retrain models
→ push WebSocket alerts`. No Celery, no Redis.

---

## How to run it

### Path A — Docker Compose (whole stack)

```powershell
Copy-Item .env.example .env        # once
docker compose up -d --build       # db → backend (runs migrations) → frontend
docker compose exec backend python -m app.seed.seed   # demo data, once healthy
```

- Frontend: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>
- Health:   <http://localhost:8000/health>
- Seeded logins (password `demo-pass-123`):
  `demo@example.com` (personal model) · `new@example.com` (population fallback)

### Path B — local backend, local frontend

```powershell
docker compose up -d db            # postgres+pgvector on localhost:5432
cd backend
.\.venv\Scripts\Activate.ps1       # a venv already exists here
$env:DATABASE_URL = "postgresql+psycopg://aq:aq@localhost:5432/aq"
$env:JWT_SECRET   = "local-dev-secret"
alembic upgrade head
uvicorn app.main:app --reload
# separate shell:
cd frontend ; npm install ; npm run dev
```

### Tests (no services needed — runs on SQLite)

```powershell
cd backend ; .\.venv\Scripts\python.exe -m pytest -q     # 47 passed
cd frontend ; npm run typecheck ; npm run lint ; npm run build
```

`COMMANDS.md` is the exhaustive reference; the above is the short version.

---

## Configuration (`.env`)

| Variable | Meaning | Safe default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy URL. Host `db` inside Compose, `localhost` locally. | compose value |
| `JWT_SECRET` | HS256 signing secret for access tokens. | must be set |
| `ACCESS_TOKEN_TTL_MINUTES` / `REFRESH_TOKEN_TTL_DAYS` | token lifetimes | 15 / 14 |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | OpenAI-compatible endpoint for advisory *rephrasing only*. Blank ⇒ deterministic template renderer. | blank |
| `SCHEDULER_ENABLED` | master switch for the in-process ingestion loop | `true` (tests: `false`) |
| `SYNTHETIC_INGEST` | emit synthetic gappy readings instead of calling OpenAQ | `true` |
| `INGEST_INTERVAL_MINUTES` | scheduler period (min 60s enforced) | `20` |
| `OPENAQ_BASE_URL` / `OPENWEATHER_API_KEY` | real ingestion sources (best-effort) | OpenAQ v3 / blank |

The `.env` in this repo is git-ignored and contains a throwaway local key — treat
it as disposable, not a secret to protect.

---

## Run status (last verified in this environment)

- `backend` pytest: **47 passed** (SQLite, ~49s).
- Docker image build: backend image is large (pulls `torch` for
  `sentence-transformers`); first `docker compose up --build` takes several
  minutes. Frontend image builds in well under a minute.
- See each subdirectory's `explanation.md` for what that part is responsible for.
