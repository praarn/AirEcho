# explanation.md — backend/

FastAPI service. Python 3.12, Pydantic v2, **synchronous** SQLAlchemy 2.0,
Alembic, scikit-learn, and a `pgvector`-backed RAG layer. No Celery / Redis — the
one background job is a plain asyncio task.

Deeper walkthroughs live in `app/api/`, `app/services/`, `app/ml/`, `app/rag/`,
`app/seed/`, `alembic/`, and `tests/`, each with its own `explanation.md`.

---

## Top-level files in `app/`

| File | Responsibility |
|---|---|
| `main.py` | Builds the `FastAPI` app: CORS (open in dev), mounts `/uploads` static dir, includes every router, and a `lifespan` that starts/stops the scheduler. Also `GET /health` and `GET /`. |
| `config.py` | `Settings(BaseSettings)` — every knob comes from the environment / `.env`. `settings` is a module-level singleton (`lru_cache`). `is_sqlite` property switches dialect-specific code paths. |
| `database.py` | `engine` + `SessionLocal` + `Base`. `get_db()` is the FastAPI dependency. **`EmbeddingType`** is a `TypeDecorator` that is a real `pgvector.Vector(384)` on PostgreSQL and a JSON-encoded float list on SQLite, so the test suite needs no Postgres. |
| `models.py` | All ORM tables (see below). |
| `schemas.py` | Pydantic v2 request/response models. `ORM` base sets `from_attributes=True`. |

---

## Data model (`models.py`)

```
users ──< refresh_tokens            rotating refresh-token chain w/ reuse detection
users ──< user_locations ──> stations (nearest, with distance_km stored)
stations ──< aqi_readings           raw, stored EXACTLY as reported (natural-key upsert)
weather_daily                       per-location daily temp / humidity / rain
user_locations ──< exposure_windows 6h/24h/72h aggregates + data_coverage_pct
users ──< symptom_logs              0..10 severity, optional peak-flow + OCR confidence
risk_models                         versioned; user_id NULL ⇒ population fallback
users ──< risk_predictions          persisted score + lag features + explanation
guideline_documents ──< guideline_chunks (embedding column)  WHO / CPCB corpus
users ──< advisory_log              every RAG answer, retrieved chunks, refused flag
ingestion_events                    ok | gap | failure | station_silent  (gaps are data)
audit_log                           register / data_export / data_delete
```

Privacy-relevant detail: every table holding personal health data carries a
non-null `user_id`, and the API layer *always* filters by the authenticated user
(`app/api/deps.py::scoped`). The population trainer reads through
`aggregate_training_frame()`, which never adds a `user_id` column.

---

## Request lifecycle

1. `main.py` routes the path to a router in `app/api/routes/`.
2. Endpoints touching user data depend on `CurrentUser` (decodes the JWT) and
   query through `scoped(db, Model, user.id)` — a `SELECT` already constrained to
   the caller. `get_owned_or_404` returns **404 (not 403)** for another user's id
   so existence isn't leaked.
3. Handlers call into `app/services/`, `app/ml/`, or `app/rag/`.
4. Responses are Pydantic models from `schemas.py`.

## Background lifecycle

`main.py` lifespan → `scheduler.start()` launches `_loop()`:
`ingest → materialize_all → retrain_everything → evaluate_and_push_alerts`,
every `INGEST_INTERVAL_MINUTES` (≥ 60s). All DB work is sync and runs in a
threadpool so it never blocks the event loop or WebSocket sends. Disabled in
tests via `SCHEDULER_ENABLED=false`.

---

## Dialect strategy (why sync SQLAlchemy + a type shim)

The suite runs on a throwaway SQLite file (`tests/conftest.py`) so contributors
need nothing installed; CI *also* runs the identical suite against real
`pgvector/pgvector:pg16`. Two places branch on `db.bind.dialect.name`:

- `database.py::EmbeddingType` — `Vector` vs `Text(JSON)`.
- `rag/retrieve.py` — pgvector `cosine_distance` ordered in SQL vs NumPy cosine
  over all rows.
- `services/ingestion.py::_upsert_reading` — `ON CONFLICT` vs select-then-update.

---

## Running & testing

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pytest -q          # 47 passed, no services needed
.\.venv\Scripts\python.exe -m ruff check .       # lint (CI: ruff check app tests)

# against real Postgres:
docker compose up -d db
$env:DATABASE_URL = "postgresql+psycopg://aq:aq@localhost:5432/aq"
$env:JWT_SECRET = "local-dev-secret"
alembic upgrade head
uvicorn app.main:app --reload
```

`Dockerfile` installs `tesseract-ocr` + Pillow/torch runtime libs, `pip install
-e ".[dev]"`, and pre-downloads the MiniLM embedding model so the first RAG call
isn't slow. The image is large because `sentence-transformers` pulls `torch`.
