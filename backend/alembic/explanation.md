# explanation.md — backend/alembic/

Database schema migrations.

```
alembic/
├── env.py                 wires Alembic to app.config.settings + Base.metadata
├── script.py.mako         migration template
└── versions/
    └── 0001_initial.py    the whole schema in one revision
```

## `env.py`

- Pulls the URL from `app.config.settings.database_url` (so `alembic` obeys the
  same `.env` / env vars as the app — no separate DB config).
- `import app.models` registers every table on `Base.metadata`, which is the
  `target_metadata` for autogenerate.
- `compare_type=True` so column-type changes are detected.
- Standard online/offline split.

## `versions/0001_initial.py`

Single revision creating every table in `app/models.py`. On PostgreSQL it also
`CREATE EXTENSION IF NOT EXISTS vector` and creates the `guideline_chunks.embedding`
column as a real `vector(384)`. There is no second migration yet — schema changes
so far have been folded back into this one during development.

## Commands

```powershell
alembic upgrade head       # apply (the backend container runs this on start)
alembic downgrade -1       # roll back one
alembic current            # show applied revision
alembic history            # revision graph
alembic revision --autogenerate -m "message"   # after editing app/models.py
```

The Compose `backend` service runs `alembic upgrade head` before `uvicorn`. The
pytest suite does **not** use Alembic — `tests/conftest.py` calls
`Base.metadata.create_all()` directly against SQLite. CI runs `alembic upgrade
head` against real Postgres as a separate check.
