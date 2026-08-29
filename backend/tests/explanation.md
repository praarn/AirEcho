# explanation.md — backend/tests/

Pytest + FastAPI `TestClient`. **47 tests**, run in ~50s, need no services.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest tests/test_exposure_windows.py    # one suite
.\.venv\Scripts\python.exe -m pytest -k "isolation or auth"            # by keyword
```

## `conftest.py`

Sets env **before** any app import: `DATABASE_URL=sqlite+pysqlite:///./_test_aq.db`,
a throwaway `JWT_SECRET`, `SCHEDULER_ENABLED=false`, `SYNTHETIC_INGEST=false`,
`LLM_API_KEY=""`. Deletes the SQLite file, then `Base.metadata.create_all()`.

Fixtures: `_clean_tables` (autouse — truncates every table after each test),
`db` (a `Session`), `client` (`TestClient`), `auth` (registers + logs in
`a@example.com`, sets the bearer header on the client), `user_a` / `user_b`
(token dicts for isolation tests).

The SQLite path is real coverage, not a shortcut: `EmbeddingType` degrades to
JSON text and `retrieve()` falls back to NumPy cosine, so the RAG ranking logic
still runs. CI additionally runs this identical suite against
`pgvector/pgvector:pg16`.

## The suites

| File | What it locks down |
|---|---|
| **`test_exposure_windows.py`** | *Centerpiece #1.* Synthetic readings with deliberate holes; `data_coverage_pct` and the rolling averages are computed against the data that actually exists — never as if the gap weren't there. Values checked against hand computation. |
| **`test_lag_features.py`** | *Centerpiece #2.* The t-0 / t-6h / t-24h / t-72h features are pulled from the correct historical sub-windows; plus insufficient-history and gap-straddling edge cases. |
| `test_risk_model.py` | Time-based split really is chronological (`max(train.logged_at) <= min(test.logged_at)`); the personal/population threshold gate; the population frame has **no `user_id` column**. |
| `test_rag.py` | Embedder + LLM both mocked. Every non-refused answer carries ≥ 1 citation; out-of-corpus questions are refused; an answer with an untraceable number falls back to the grounded template renderer. |
| `test_isolation.py` | User A gets **404** (not 403) on every one of user B's resources, across every endpoint; can't mutate them either. |
| `test_auth.py` | register → login → `/me`; duplicate-email 409; refresh-token **rotation** and reuse-detection revoking the chain. |
| `test_ocr.py` | A low-confidence or implausible read is always flagged `needs_confirmation`, never silently trusted. Skips cleanly when `tesseract` isn't on PATH. |
| `test_websocket.py` | Connect → threshold-triggered push → the reconnect-then-REST contract. |
| `test_health.py` | `/health`, `/openapi.json`, and a full register→location→symptom→materialize→score→advisory smoke test through the public API. |

## Lint / format (matches CI)

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```
