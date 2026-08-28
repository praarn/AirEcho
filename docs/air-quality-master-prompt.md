# Master Prompt — Air Quality – Health Risk Correlator

> Copy everything below into Claude Code (or Claude with computer/file tools) as your project brief.
> It's written to be handed over in one shot, then worked through phase by phase — tell Claude
> "start with Phase 1" rather than asking for everything at once in a single response.

---

You are helping me build a full-stack, portfolio-grade project called the **Air Quality – Health Risk
Correlator**. Read this entire brief before writing any code. Build it phase by phase, in the order
given at the end — do not skip ahead or generate the whole app in one pass. After each phase, stop,
summarize what was built, list any assumptions you made, and wait for me to confirm before
continuing.

## What this project is

Generic AQI apps show the same number to everyone. The core engineering problem here is different and
harder: **align three genuinely irregular time series** — sensor readings on their own polling
cadence, weather on another cadence, and user-logged symptoms logged whenever the user happens to log
them — into a feature space that can honestly support a **lagged** model (exposure at t-0/t-6h/t-24h
predicting symptom severity), without ever pretending the underlying data is cleaner or more complete
than it is. The personalized-risk-modeling and honest-time-alignment work is the main deliverable. The
RAG advisory layer is a secondary feature whose entire value depends on never letting the LLM invent a
health threshold that isn't traceable to a retrieved WHO/CPCB passage.

## Hard constraints — do not deviate from these

**Tech stack (exactly this, nothing else):**
- Frontend: Next.js 15/16, TypeScript, Tailwind CSS
- Backend: Python, FastAPI, Pydantic (v2)
- Database: PostgreSQL (with the `pgvector` extension for RAG — do NOT add a separate vector
  database, do NOT add Redis or Celery; use FastAPI `BackgroundTasks` or a plain `asyncio` scheduling
  loop for ingestion jobs)
- AI/Data: Python, Pandas, NumPy, scikit-learn (lagged linear regression baseline, then
  `RandomForestRegressor`), an OCR tool (Tesseract, with a vision-LLM call as a documented fallback for
  low-confidence images), an LLM API (assume an OpenAI-compatible or Anthropic API via an environment
  variable — never hardcode a key), RAG via `sentence-transformers` + `pgvector`
- Auth: JWT access tokens (short-lived) + refresh tokens, rotated on every use
- Infra: Docker + Docker Compose only — **no Kubernetes, no Jenkins, no Helm, no Terraform**
- CI: GitHub Actions only
- Testing: Pytest + FastAPI TestClient

**Non-negotiable engineering principles:**
1. Never compute a rolling exposure average as if a data gap didn't exist. Every exposure window
   stores an explicit `data_coverage_pct` reflecting actual reporting gaps, and this coverage measure
   is surfaced all the way to the UI, not just handled invisibly in the pipeline.
2. Model lag explicitly: features must include exposure at t-0, t-6h, and t-24h (minimum) as distinct
   inputs feeding a single prediction of current/near-term symptom severity — this is the entire point
   of the project, not same-day correlation.
3. Time-based train/test splits only, never random splits, for any model trained on this data — assert
   this in tests, not just claim it in comments.
4. A brand-new user without enough personal history must fall back to a clearly-labeled
   population-level model, never a personalized-looking prediction built on 3 data points. Define and
   document a minimum-data threshold and enforce it in code.
5. The RAG advisory layer must never let the LLM state a numeric threshold, limit, or health claim
   that isn't directly traceable to a retrieved WHO/CPCB chunk. Every advisory response carries
   inline citations. When retrieval doesn't clearly cover the user's situation, the system says so
   explicitly rather than letting the LLM improvise — this matters more here than in your other
   projects because it's health-adjacent content.
6. OCR-extracted peak-flow values below a confidence threshold are never silently trusted — they're
   flagged for the user to manually confirm or correct before being used in any model or chart.
7. Per-user data isolation is enforced at the query layer itself (scoped by authenticated user_id in
   every query), never just trusted from request parameters. Any population-level model training uses
   only anonymized/aggregated data, and the aggregation step must strip user_id before training.
8. Be explicit, in code comments and the README, that self-reported symptom severity correlated with
   lagged exposure is exactly that — correlational, small-sample, and noisy — not causal inference.
   Do not let any UI copy or documentation overclaim what the model actually demonstrates.
9. Write tests as you build each feature. The exposure-window gap-handling test suite and the
   lag-feature construction test suite are the centerpieces of this project's tests — treat them with
   real care, same as the corresponding "messy real data" test suites in your other projects.

## Full feature list

Use the feature spec below as the definitive scope. Ask me before adding anything not listed here.

[Paste the full contents of `air-quality-features.md` here before sending this prompt — sections 1
through 11, covering: AQI and weather ingestion, the exposure-window alignment pipeline, symptom
logging with peak-flow OCR, personalized lagged risk modeling with a population fallback, grounded RAG
advisory, WebSocket live alerts, the dashboard, auth and privacy, testing, infra/CI, and
resume-worthy metrics.]

## Data model expectations (adjust as needed, but keep this shape)

```
users(id, email, hashed_password, created_at)
refresh_tokens(id, user_id, token_hash, revoked, expires_at, created_at, user_agent)
stations(id, source, location_name, lat, lng)
aqi_readings(id, station_id, pollutant, value, recorded_at, ingested_at)
weather_daily(id, location, date, temp, rainfall, humidity, source_station)
user_locations(id, user_id, label, lat, lng, nearest_station_id, distance_km, resolved_at)
symptom_logs(id, user_id, severity, notes, peak_flow_value, peak_flow_photo_url,
             ocr_confidence, manually_confirmed, logged_at)
exposure_windows(id, user_id, location_id, window_type['6h'|'24h'|'72h'], window_start,
                 window_end, avg_pm25, avg_no2, avg_o3, avg_temp, avg_humidity,
                 data_coverage_pct, computed_at)
risk_models(id, user_id nullable, model_type['personal'|'population_fallback'], model_version,
            trained_at, mae, feature_importance_json)
risk_predictions(id, user_id, model_id, predicted_at, risk_score, lag_features_json,
                 explanation_json)
guideline_documents(id, title, source_url, uploaded_at)
guideline_chunks(id, doc_id, chunk_text, embedding vector(...), section_ref)
advisory_log(id, user_id, question_or_context, retrieved_chunks_json, response_text,
             citations_json, refused boolean, created_at)
audit_log(id, actor_id, action, target_table, target_id, created_at)
```

## Build phases — work through these in order, one at a time

**Phase 0 — Foundation**
Scaffold the repo structure, Docker Compose (postgres w/ pgvector, backend, frontend), FastAPI app
skeleton with health check, Next.js skeleton with Tailwind configured, `pydantic-settings` config,
Alembic set up, GitHub Actions workflow running lint + pytest against a real Postgres service
container + frontend build. Get CI green on an empty-but-real skeleton before building features.

**Phase 1 — Auth & privacy foundation**
JWT access/refresh implementation with rotation, per-user data isolation enforced at the query layer,
data-export and data-deletion endpoints for a user's own health data, full test coverage of
login/refresh flows plus explicit cross-user isolation tests (user A cannot read user B's data via any
endpoint).

**Phase 2 — Ingestion (AQI + weather)**
Scheduled `asyncio`/`BackgroundTasks` polling for OpenAQ (and CPCB where available) and weather,
station metadata with nearest-station resolution per user-location, dedup/upsert on natural keys,
ingestion gap/failure logging (a station going silent is itself logged, never a silent hole in the
data).

**Phase 3 — Exposure window pipeline (a core deliverable)**
Pandas/NumPy rolling window computation (6h/24h/72h) per user-location, explicit `data_coverage_pct`
reflecting actual reporting gaps (not computed as if gaps didn't exist), weather features joined into
the same windows, fully reproducible materialization from raw `aqi_readings`. Build a fixture set of
synthetic AQI readings with deliberate gaps before writing tests, and use it as the primary test suite
for this phase — assert coverage percentages and rolling averages are computed correctly against
actual available data.

**Phase 4 — Symptom logging**
Text + severity symptom log entry, peak-flow meter photo upload with OCR extraction, confidence
scoring, confirm-or-correct flow for low-confidence reads, manual override always available, symptom
history view on the same time axis as exposure windows.

**Phase 5 — Lagged risk modeling (the other core deliverable)**
Lag-feature construction (t-0/t-6h/t-24h) with tests covering insufficient-history and
gap-straddling edge cases, lagged linear regression baseline, `RandomForestRegressor` as the primary
per-user model once enough data exists, a documented minimum-data threshold gating personal vs
population-fallback models, population-fallback model trained on anonymized aggregated data with
user_id stripped before training, feature importance exposed via API, strict time-based train/test
split (test this explicitly — assert no future data leaks into training), MAE reporting for both
personal and fallback models.

**Phase 6 — Grounded RAG advisory**
Chunk + embed WHO Air Quality Guidelines and CPCB advisory documents with `sentence-transformers`,
store via `pgvector`, retrieval-grounded advisory generation combining a user's current exposure/risk
output with retrieved guideline passages, inline citations on every response, explicit refusal/hedge
behavior when retrieval doesn't clearly cover the situation. Build a small hand-written eval set
(questions with known correct citations) and test against it. Mock the LLM call in unit tests and
assert citation presence and correct refusal behavior.

**Phase 7 — WebSocket live alerts**
Per-user WebSocket connection subscribed to registered locations, push on new-reading-crosses-
threshold or meaningful risk-score update, reconnect-then-REST-then-resume handling, an admin/demo
live feed view. Test connection, threshold-triggered push, and reconnect behavior.

**Phase 8 — Dashboard & polish**
Personal dashboard (current AQI, personal vs fallback risk score clearly labeled, exposure trend
charts, symptom timeline overlay), "why this risk score" feature-importance panel, data
coverage/freshness indicators wherever a number appears, grounded advisory panel with visible
citations, seed script with realistic synthetic gappy AQI data, weather data, sample users with
symptom history, and indexed guideline documents for instant demo-readiness, README documenting
architecture decisions and real measured metrics — especially the honest note that this models
correlation with lagged features, not causation.

## What I want from you at each phase

- Working code, not pseudocode — actual files, actual tests that run.
- A short rationale for any non-obvious design decision (e.g., why time-based split matters here, how
  the minimum-data threshold for personal models was chosen, why the RAG layer refuses rather than
  guesses on out-of-corpus questions).
- A list of what you assumed or simplified, so I can correct course early.
- Don't move to the next phase until I say go.

Start with Phase 0.
