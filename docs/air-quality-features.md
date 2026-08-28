# Air Quality – Health Risk Correlator — Feature Spec

## What makes this project unique
Every AQI app shows the same number to everyone. This project's core IP is tying a **person's own
exposure history to their own symptom pattern**, with the modeling done honestly (lagged features,
not same-day correlation) and the advisory text grounded in cited WHO/CPCB guideline documents rather
than an LLM improvising thresholds. The hard engineering problem — and the thing worth talking about
in an interview — is **aligning three genuinely irregular time series** (sensor readings on their own
polling cadence, weather on another, user-logged symptoms whenever the user happens to log them) into
a single feature space a model can actually learn from, without silently pretending the alignment is
cleaner than it is.

Tech stack fixed per your requirements: Next.js 15/16 + TypeScript + Tailwind, FastAPI + Pydantic,
PostgreSQL (+ pgvector for RAG — no separate vector DB), Docker Compose, GitHub Actions, Pytest +
TestClient, JWT access/refresh with rotation. No Kubernetes, no Jenkins.

---

## 1. Live Data Ingestion — AQI & Weather

### 1.1 AQI ingestion
- [ ] Scheduled polling job (FastAPI `BackgroundTasks` loop or a plain `asyncio` scheduler — no
      Celery, no Kubernetes CronJobs) pulling live readings from OpenAQ (and CPCB where available)
      on an interval (e.g., every 15–30 min)
- [ ] Store raw readings per station/pollutant with `recorded_at` exactly as reported — never
      overwrite or "clean up" the raw feed on ingest
- [ ] Station metadata table (location, coordinates, source) so readings can be mapped to users by
      nearest-station distance, with that distance stored and surfaced (never silently assume a
      station is "close enough")
- [ ] Ingestion failure/gap logging: if a station stops reporting, that's itself a signal — log it,
      don't just leave a silent hole in the data
- [ ] Deduplication on `(station_id, pollutant, recorded_at)` with upsert semantics for
      republished/corrected readings

### 1.2 Weather ingestion
- [ ] Parallel scheduled pull from IMD/OpenWeatherMap per relevant location, same cadence discipline
      as AQI ingestion, stored with source/station metadata

### 1.3 Per-user location handling
- [ ] Users register one or more locations (home, work) with lat/lng
- [ ] Nearest-station resolution computed and cached per user-location pair, with distance stored —
      re-resolved if a closer station comes online later

---

## 2. Exposure Window Pipeline (Pandas/NumPy) — the alignment problem

- [ ] Rolling exposure window computation per user-location: 6h, 24h, 72h windows for each tracked
      pollutant (PM2.5, PM10, NO2, O3, etc.), computed from the nearest station's raw readings
- [ ] Explicit handling of **irregular polling gaps**: if a station's readings have gaps, the rolling
      average must reflect actual data coverage (e.g., store `data_coverage_pct` per window, not just
      a number computed as if the gap didn't exist) — this is the "honest about irregular time series"
      story, make it visible in the schema and the API response, not just handled invisibly in code
- [ ] `exposure_windows` table materialized on a schedule (same job cadence as ingestion, or
      triggered after each new ingestion batch), fully reproducible by rerunning the pipeline against
      raw `aqi_readings`
- [ ] Weather features joined into the same window (avg temp, humidity, rainfall over the window) —
      useful both as model features and as context in the UI ("high humidity days show your symptoms
      trending up," etc., if the data actually supports that — don't state a pattern the model
      doesn't back)

---

## 3. Symptom Logging (multimodal input)

- [ ] Free-text symptom log entry (severity scale + notes), timestamped
- [ ] Peak-flow meter photo upload: OCR extraction of the numeric reading (Tesseract, or a small
      vision-LLM call as a fallback for low-quality images) — be explicit in the README that this is
      OCR digit-reading, not a sophisticated vision model, and that's a deliberate, honest scoping
      choice, not a limitation to hide
- [ ] OCR confidence score stored per reading; low-confidence extractions flagged for the user to
      manually confirm/correct before the value is used in any model (never silently trust a
      low-confidence OCR read as ground truth)
- [ ] Manual override: user can always correct a misread peak-flow value directly
- [ ] Symptom log history view per user, correlated against the same time axis as their exposure
      windows (useful both for the model and for the user's own pattern-spotting)

---

## 4. Personalized Risk Modeling (sklearn) — the "not a black box" story

- [ ] Lagged feature construction: exposure at t-0, t-6h, t-24h (and optionally t-72h) as separate
      model inputs — explicitly modeling *lag*, not same-day correlation, is the whole point; say this
      clearly in code comments and README
- [ ] Start with a lagged linear regression baseline (interpretable, easy to sanity-check), then a
      `RandomForestRegressor` as the primary model once there's enough per-user data — document the
      minimum data threshold you require before trusting a personalized model over a generic
      population-level fallback (be honest that a brand-new user with 3 symptom logs doesn't have
      enough data for a meaningful personal model)
- [ ] Feature importance / coefficient reporting exposed via API — this is your "personalized risk
      signal," not a bare severity-score output. Show which lag window and which pollutant is driving
      a given prediction
- [ ] Per-user model retraining on a schedule (or triggered after N new symptom logs), versioned so
      you can compare model performance over time as more data accumulates
- [ ] Population-level fallback model (trained across all users' anonymized exposure/symptom pairs)
      for users without enough personal history yet — clearly labeled as "general pattern, not yet
      personalized to you" in the UI, never presented as if it were personal
- [ ] Model evaluation: time-based train/test split (never random — symptom severity is a time
      series), report MAE against held-out data, and be honest in the README about the real limitation
      here: self-reported symptom severity is noisy, small-sample, and correlational even with lagged
      features — this isn't causal inference, and saying that explicitly is a stronger engineering
      signal than pretending otherwise

---

## 5. RAG — Grounded Health Advisory (WHO/CPCB, Not LLM Guessing)

- [ ] Chunk + embed WHO Air Quality Guidelines PDF and CPCB advisory documents using
      `sentence-transformers`, stored via `pgvector` in the same Postgres instance
- [ ] Retrieval-grounded advisory generation: given a user's current exposure level + risk model
      output, retrieve the relevant guideline passages and have the LLM **rephrase/contextualize
      only what's retrieved** — the LLM must never state a numeric threshold, limit, or health claim
      that isn't traceable to a retrieved chunk
- [ ] Every advisory response includes inline citations back to the specific guideline document and
      section — no unattributed health claims anywhere in the UI
- [ ] Explicit refusal/hedge behavior when retrieval doesn't clearly cover the user's specific
      situation (e.g., an unusual pollutant combination not well covered in the indexed docs) — say
      "the available guidelines don't specifically address this" rather than having the LLM improvise
- [ ] A lightweight eval set: a handful of hand-written questions with known correct guideline
      citations, used to sanity-check that retrieval is actually working before you trust the pipeline
      in a demo

---

## 6. Live Alerts (WebSocket — genuinely justified here)

- [ ] WebSocket connection per logged-in user, subscribed to their registered location(s)
- [ ] Push a message when: a new AQI reading crosses a threshold relevant to that user (e.g., their
      personal risk model or a general WHO guideline threshold), or their computed personal risk
      score updates meaningfully
- [ ] Reconnection handling: on reconnect, client fetches current state via REST first, then resumes
      live updates via WebSocket — don't rely on WebSocket alone for state, it's a push channel on
      top of a REST source of truth
- [ ] Admin/demo view: a live feed of raw incoming readings across all tracked stations, useful for
      demoing the ingestion pipeline is actually live

---

## 7. Dashboard & UX

- [ ] Personal dashboard: current AQI at nearest station, current personal risk score (with the
      "population fallback" vs "personalized" label made clear), exposure trend chart across 6h/24h/72h
      windows, symptom log timeline overlaid on the same time axis
- [ ] "Why this risk score" panel showing the feature-importance breakdown from Section 4 — never a
      bare number with no explanation
- [ ] Data coverage/freshness indicators wherever a number is shown (ties back to
      `data_coverage_pct` from Section 2 — a gappy data period should visibly look gappy, not
      falsely confident)
- [ ] Grounded advisory panel (Section 5) with visible citations
- [ ] Symptom log entry flow including peak-flow photo capture/upload with OCR-confirm-or-correct
      step before saving

---

## 8. Auth & Privacy

- [ ] JWT access (short-lived) + refresh token, rotated on every use — same pattern as your other
      projects, appropriate here since this is personal health data
- [ ] Per-user data isolation enforced at the query layer, not just trusted from request params —
      a user can only ever read their own symptom logs and exposure windows
- [ ] Explicit data-export and data-deletion endpoints for the user's own health data (a real privacy
      feature, not just a nice-to-have — worth having given this is health-adjacent data)
- [ ] Population-level model training uses anonymized/aggregated data only — document exactly what's
      stripped before aggregation (no user_id joined into the training set used for the fallback model)

---

## 9. Testing (Pytest + FastAPI TestClient)

- [ ] Exposure window pipeline tests: synthetic AQI readings with deliberate gaps, assert
      `data_coverage_pct` and rolling averages are computed correctly against the actual available
      data, not as if gaps didn't exist
- [ ] Lag-feature construction tests: assert t-0/t-6h/t-24h features are correctly pulled from the
      right historical windows, including edge cases (insufficient history, straddling a data gap)
- [ ] Risk model tests: time-based train/test split correctness (assert no future data leaks into
      training), assert the population-fallback path triggers correctly below the minimum-data
      threshold
- [ ] OCR pipeline tests: known peak-flow meter images with expected extracted values, assert
      low-confidence results are flagged for manual confirmation rather than silently accepted
- [ ] RAG tests: mock the LLM call, assert every generated advisory includes at least one citation,
      assert the refusal path triggers on an out-of-corpus question from your eval set
- [ ] WebSocket tests: connect, verify a pushed message arrives on a simulated new reading crossing
      threshold, verify reconnect-then-REST-then-resume behavior
- [ ] Auth/privacy tests: standard login/refresh/rotation coverage, plus explicit tests that user A
      cannot read user B's symptom logs or exposure windows via any endpoint

---

## 10. Infra & CI/CD

- [ ] `docker-compose.yml`: `postgres` (with pgvector extension), `backend`, `frontend`
- [ ] `pydantic-settings` config, no hardcoded secrets/API keys
- [ ] GitHub Actions: lint → pytest (Postgres service container with pgvector enabled) → frontend
      typecheck/build → `docker compose build` sanity check
- [ ] Alembic migrations
- [ ] Seed script with a realistic (synthetic-if-needed) sample of AQI readings with deliberate gaps,
      weather data, a few sample users with symptom log history, and the WHO/CPCB guideline documents
      indexed, so a fresh clone is demoable in minutes

---

## 11. Metrics worth capturing for your resume / interview talking points

- [ ] Average data coverage % across tracked stations, and how imputation/gap-handling affects
      exposure-window accuracy
- [ ] Personalized model MAE vs population-fallback model MAE, per user, once enough data exists —
      showing the personalized model actually outperforms the generic one is a real, checkable claim
- [ ] Minimum data threshold you settled on before trusting a personal model, and why (document the
      reasoning, not just the number)
- [ ] RAG groundedness: citation-presence rate and correct-refusal rate on your hand-written eval set
- [ ] OCR extraction accuracy against a small hand-labeled peak-flow-photo test set (report sample
      size honestly)

---

## Suggested build order

1. Auth + Docker + CI skeleton (shared foundation, same as your other projects)
2. AQI + weather ingestion, station metadata, gap/failure logging, dedup/upsert
3. Exposure window pipeline with honest gap/coverage handling (the core differentiator — get this
   right before any modeling)
4. Symptom logging (text + peak-flow photo OCR with confirm-or-correct flow)
5. Risk modeling: lagged linear regression baseline → RandomForest, population-fallback path, proper
   time-based evaluation
6. RAG grounded advisory layer (reuse the pgvector pattern if you've built it in another project)
7. WebSocket live alerts
8. Dashboard + polish: seed data, README with your honest scoping notes (especially on the
   correlational-not-causal limitation) and real measured metrics
