# Commands

Every command needed to run, seed, test, and inspect the project. Two paths:

- **Path A — Docker Compose** (recommended): the whole stack in one command.
- **Path B — Local dev**: backend in a venv + frontend with npm, Postgres in Docker.

Paths are written for **Windows PowerShell** (this repo's primary shell); the
Bash equivalent is given where it differs. Run everything from the repo root
`D:\resume\air-quality` unless a step says otherwise.

---

## 0. Prerequisites

| Tool | Version used here | Check |
|------|-------------------|-------|
| Docker + Compose | Docker 29.x, Compose v5.x | `docker --version` · `docker compose version` |
| Node.js | v24 (CI uses 20) | `node --version` |
| Python | 3.12+ (container is 3.12; local venv here is 3.14) | `python --version` |

One-time: create the env file (safe defaults; fill `LLM_API_KEY` only if you want
live advisory text — the app degrades to a deterministic renderer without it).

```powershell
Copy-Item .env.example .env
```
```bash
cp .env.example .env
```

---

## Path A — Docker Compose (full stack)

### A1. Build & start

```powershell
docker compose up -d --build
```

Startup order is healthcheck-gated: `db` (waits for `pg_isready`) → `backend`
(runs `alembic upgrade head`, then `uvicorn`) → `frontend`.

### A2. Seed a demoable state (run once, after the stack is healthy)

```powershell
docker compose exec backend python -m app.seed.seed
```

Creates: WHO + CPCB guideline chunks embedded into pgvector · 4 stations with
~35 days of deliberately gappy synthetic AQI · synthetic weather ·
`demo@example.com` (48 symptom logs over 25 days → clears the personal-model
threshold) · `new@example.com` (4 logs → population fallback only) · materialized
exposure windows · trained models · regenerated `docs/METRICS.md`.

### A3. Open it

| URL | What |
|-----|------|
| http://localhost:3000 | Frontend |
| http://localhost:8000/docs | Interactive API docs |
| http://localhost:8000/health | Scheduler + last-ingest status |

Seeded logins (password `demo-pass-123` for both):
`demo@example.com` (personal model) · `new@example.com` (population fallback).

### A4. Everyday Compose commands

```powershell
docker compose ps                      # container status + ports
docker compose logs -f backend         # follow backend logs
docker compose logs -f frontend
docker compose logs --tail 50 db
docker compose restart backend
docker compose exec backend sh         # shell inside the backend container
docker compose down                    # stop + remove containers (keeps the pgdata volume)
docker compose down -v                 # also delete the database volume (full reset)
docker compose up -d --build backend   # rebuild just one service
```

### A5. Trigger one ingestion → materialize → retrain cycle on demand

```powershell
# via the API (needs a bearer token — grab one from /docs or the login call in B7)
curl -X POST http://localhost:8000/ingestion/run -H "Authorization: Bearer <ACCESS_TOKEN>"
```

The background scheduler also runs this automatically every
`INGEST_INTERVAL_MINUTES` (default 20).

---

## Path B — Local dev (backend venv + frontend npm)

### B1. Database (still via Docker — the app needs Postgres + pgvector)

```powershell
docker compose up -d db
```

This publishes Postgres on `localhost:5432` (user/password/db all `aq`).

### B2. Backend — create / activate the virtualenv

A venv already exists at `backend\.venv`. To recreate from scratch:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```
```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate      # Git Bash on Windows
pip install -e ".[dev]"
```

> The RAG layer also needs `sentence-transformers` (in `pyproject.toml` but heavy).
> `pip install -e ".[dev]"` installs it. If you skipped it, the test suite still
> passes (it mocks the embedder), but `/advisory/ask` and `python -m app.rag.eval`
> will fail until you `pip install sentence-transformers`.

### B3. Point the backend at local Postgres and run migrations

The `.env` `DATABASE_URL` uses host `db` (Compose-only). Override it for local runs:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://aq:aq@localhost:5432/aq"
$env:JWT_SECRET   = "local-dev-secret-change-me"
alembic upgrade head
```
```bash
export DATABASE_URL=postgresql+psycopg://aq:aq@localhost:5432/aq
export JWT_SECRET=local-dev-secret-change-me
alembic upgrade head
```

### B4. Run the backend

```powershell
uvicorn app.main:app --reload
```

If the venv isn't activated, prefix with the venv interpreter:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

API now on http://localhost:8000 (`--reload` also starts the in-process scheduler
unless you set `$env:SCHEDULER_ENABLED = "false"`).

### B5. Seed (local)

```powershell
python -m app.seed.seed
```

### B6. Frontend

```powershell
cd ../frontend
npm install            # first time (CI uses: npm ci)
npm run dev            # http://localhost:3000, proxies /api/* to :8000
```

Production-style local run:

```powershell
npm run build
npm run start          # serves the built app on :3000
```

### B7. Get an access token from the CLI (for curl / WebSocket testing)

```bash
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"demo-pass-123"}'
```

---

## Tests, lint, typecheck, build

### Backend (from `backend/`, venv active or via `.\.venv\Scripts\python.exe -m ...`)

```powershell
python -m pytest                                  # full suite (SQLite, no Postgres needed) — 47 tests
python -m pytest -q                               # quiet
python -m pytest --cov=app --cov-report=term-missing
python -m pytest tests/test_exposure_windows.py   # one suite (CORE #1)
python -m pytest tests/test_lag_features.py       # CORE #2
python -m pytest tests/test_risk_model.py
python -m pytest tests/test_ocr.py -rP            # OCR (skips cleanly if tesseract isn't on PATH)
python -m pytest -k "isolation or auth"           # by keyword
```

Lint / format (matches CI, plus `alembic/`):

```powershell
python -m ruff check .                # lint (repo-wide)
python -m ruff check --fix .          # autofix
python -m ruff format .               # apply formatting
python -m ruff format --check .       # CI check mode
python -m ruff check app tests        # exactly what CI lints
```

### Frontend (from `frontend/`)

```powershell
npm run typecheck     # tsc --noEmit
npm run lint          # next lint (eslint)
npm run build         # next build (production)
```

### Docker build sanity (matches the CI `compose-build` job)

```powershell
docker compose build
```

---

## Utility / inspection

### RAG evaluation (needs a migrated DB with guidelines indexed — run the seed first)

```powershell
# Docker:
docker compose exec backend python -m app.rag.eval
# Local (from backend/, DATABASE_URL set):
python -m app.rag.eval
```

Prints `citation_presence_rate` and `correct_refusal_rate`.

### Regenerate `docs/METRICS.md`

Runs automatically at the end of `app.seed.seed`. To do it alone:

```powershell
docker compose exec backend python -c "from app.database import SessionLocal; from app.ml.train import write_metrics_doc; write_metrics_doc(SessionLocal())"
```

### Health / smoke checks

```bash
curl -s http://localhost:8000/health
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/docs
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/
```

### Database shell

```powershell
docker compose exec db psql -U aq -d aq
# e.g.  \dt   ·   select count(*) from aqi_readings;   ·   select * from ingestion_events order by created_at desc limit 10;
```

### Alembic

```powershell
alembic upgrade head              # apply latest
alembic downgrade -1              # roll back one
alembic current                   # show applied revision
alembic history                   # revision graph
```

---

## Full from-scratch verification sequence

What a complete build test runs, in order:

```powershell
# 1. Backend deps present in the venv
cd backend
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 2. Backend lint + tests (SQLite — no services required)
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q               # expect: 47 passed

# 3. Frontend checks
cd ..\frontend
npm ci
npm run typecheck                                     # expect: clean
npm run lint                                          # expect: no warnings or errors
npm run build                                         # expect: Compiled successfully, 8/8 static pages

# 4. Full container stack
cd ..
docker compose up -d --build
docker compose ps                                     # expect: db healthy, backend + frontend up
curl -s http://localhost:8000/health                  # expect: {"status":"ok",...}
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/   # expect: 200

# 5. Seed + verify data flows
docker compose exec backend python -m app.seed.seed
docker compose exec backend python -m app.rag.eval
```

Last verified: backend **47 passed**, `ruff` clean, frontend typecheck/lint/build
green, all three containers healthy.

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `ModuleNotFoundError: passlib` (or fastapi, sqlalchemy…) when running tests | You're using the system Python, not the venv. Use `.\.venv\Scripts\python.exe -m pytest` or activate the venv. |
| `ruff: command not found` | It's installed in the venv but maybe not on PATH — use `python -m ruff ...`. |
| Backend can't connect to DB locally (`could not translate host name "db"`) | `.env` `DATABASE_URL` is Compose-only. Override with `$env:DATABASE_URL = "postgresql+psycopg://aq:aq@localhost:5432/aq"` and run `docker compose up -d db`. |
| `/advisory/ask` 500s locally | `sentence-transformers` not installed in the venv: `pip install sentence-transformers`. (Tests still pass — they mock it.) |
| `/health` shows `aqi_rows: 0` on a fresh stack | Expected before any `user_location` exists or the seed runs — nothing for `materialize_all` to anchor on. |
| `test_ocr.py` mostly skipped | `tesseract` isn't on the host PATH. Fine locally; the backend **container** has it. |
| Port already in use (5432 / 8000 / 3000) | Stop the conflicting process or change the left side of the port mapping in `docker-compose.yml`. |
| Stale DB after schema changes | `docker compose down -v` then `docker compose up -d --build` and re-seed. |
| Leftover ad-hoc container (e.g. `aq-alembic-test`) | `docker rm -f <name>`. |
