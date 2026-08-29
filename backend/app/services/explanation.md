# explanation.md — backend/app/services/

Domain logic that isn't HTTP and isn't modelling. This is where the project's
central claim — *honest about irregular data* — is actually implemented.

```
services/
├── exposure_pipeline.py   CORE #1 — align irregular series into windows + coverage
├── ingestion.py           pull/emit raw readings + weather; log gaps, never hide them
├── scheduler.py           in-process asyncio loop: ingest → materialize → retrain
├── ocr.py                 peak-flow meter digit reading, low-confidence ⇒ confirm
└── geo.py                 haversine nearest-station resolution (distance is stored)
```

---

## `exposure_pipeline.py` — the honest-about-gaps pipeline

### The problem
Sensor readings arrive on an irregular cadence with real outages. A rolling
average computed as if the gaps weren't there is a lie.

### The solution
`compute_exposure_window(readings, window_type, window_start, window_end,
cadence_minutes, weather)` is a **pure function** (the unit under test) that
returns a `WindowResult` with:

```
expected_slots    = max(1, round(window_minutes / station.nominal_cadence_minutes))
observed_slots    = # distinct cadence-sized buckets that got >= 1 reading
data_coverage_pct = min(100, 100 * observed_slots / expected_slots)
pollutant_means   = plain mean of the data THAT EXISTS  (never divided by expected,
                    never imputed)
```

So a window that only saw 40 % of its expected readings is stored with
`data_coverage_pct = 40.0`, and that number rides along with the averages all the
way to the dashboard badge. Slot bucketing: each reading's offset from
`window_start` is integer-divided by the cadence, clipped to
`[0, expected_slots-1]`, and `nunique()` counted.

### Persistence
- `materialize_for_location(db, loc, reference_time=None)` — recompute + **upsert**
  the 6h/24h/72h windows for one user-location, anchored at `reference_time`
  (default now). Fully reproducible from raw `aqi_readings`.
- `materialize_all(db)` — loop every `user_location`, commit. Called by the
  scheduler and the seed.
- `coverage_summary(windows)` — overall %, per-window-type %, and the single worst
  window; backs `GET /exposure/coverage-summary`.

Weather is joined in loosely: daily rows within `[window_start-1d, window_end)`,
averaged, `None` if absent.

`tests/test_exposure_windows.py` builds synthetic readings with deliberate holes
and asserts both the averages and the coverage percentages against
hand-computed values.

---

## `ingestion.py` — raw data in, gaps recorded

Rules (from the brief):
- readings stored with `recorded_at` **exactly as reported** — no cleanup on
  ingest;
- dedup / upsert on the natural key `(station_id, pollutant, recorded_at)` —
  `_upsert_reading` uses `ON CONFLICT` on PostgreSQL, select-then-update on
  SQLite;
- a station that stops reporting is written as an `ingestion_events` row with
  status `station_silent` (`_flag_silent_stations`, cutoff 3h) — never a silent
  hole.

Feeds:
- **`synthetic_readings_for_station` / `ingest_synthetic`** — a diurnal PM curve
  (two rush-hour humps) + noise, with ~18 % of slots *dropped entirely* to mimic
  an intermittently-reporting sensor. Seeded RNG ⇒ reproducible. This is the
  default (`SYNTHETIC_INGEST=true`) so the pipeline always has gappy data to
  chew on offline.
- **`ingest_openaq`** (async) — best-effort OpenAQ v3; any HTTP/parse failure is
  logged as an `ingestion_events` `failure` row and the loop continues.
- **`ingest_weather_synthetic`** — sinusoidal temp/humidity/rain per station
  location, upserted on `(location, date)`.

---

## `scheduler.py` — the whole "background job" system

A plain `asyncio.Task`, started from the FastAPI lifespan when
`SCHEDULER_ENABLED=true`. No Celery, no Redis, no external process.

`_loop()`: sleep 5s (let migrations settle) → forever: `_tick()` then sleep
`max(60, INGEST_INTERVAL_MINUTES*60)`.

`_tick_sync()` (run in a threadpool so it never blocks the event loop):
`ingest_synthetic + ingest_weather_synthetic → materialize_all → retrain_everything`.
`_tick()` wraps it, then `evaluate_and_push_alerts()` and a
`broadcast_admin({type:"tick", ...})`. Any exception is caught and stored in
`_last_run` (surfaced at `GET /health`) so one bad tick never kills the loop.
`POST /ingestion/run` calls `_tick_sync()` directly for on-demand demo runs.

---

## `ocr.py` — deliberately simple, and safe about it

`extract_peak_flow(image_bytes)` → grayscale + autocontrast + Tesseract in
digit-only mode (`--psm 7 -c tessedit_char_whitelist=0123456789`), picks a
plausible 2–3 digit token in `[60, 900]` L/min, averages Tesseract's per-token
confidence.

The safety property (not a hidden limitation — documented): a read is flagged
`needs_confirmation=True` when the value is missing, confidence < 0.75, or out of
plausible range. An unconfirmed value is stored but **excluded from every model
and chart** until the user confirms/corrects it. If Tesseract isn't installed the
function returns `engine="unavailable", needs_confirmation=True` — it never
throws into the request path. `vision_llm_fallback()` is a documented opt-in stub
that *still* returns `needs_confirmation=True`.

`tests/test_ocr.py` renders digit images and asserts the flag behaviour; it skips
cleanly when `tesseract` isn't on PATH (the backend container always has it).

---

## `geo.py`

`haversine_km()` great-circle distance, and `resolve_nearest_station(db, loc)` —
linear scan over all stations returning `(station_id, round(km, 3))`. The
distance is always stored on the `user_location` and shown in the UI; the app
never silently assumes a station is "close enough".
