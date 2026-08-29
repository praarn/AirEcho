# explanation.md — backend/app/seed/

One command turns a fresh clone into a demoable state:

```powershell
docker compose exec backend python -m app.seed.seed     # Docker
python -m app.seed.seed                                  # local (DATABASE_URL set)
```

`seed.py::main()` runs, in order:

1. **`index_guidelines(db, reset=True)`** — WHO AQG 2021 + CPCB AQI corpus
   chunked and embedded into `guideline_chunks` (pgvector). *(Needs
   `sentence-transformers` installed; the test suite mocks it but the seed does
   not.)*
2. **`seed_stations`** — 4 synthetic stations around a city. "Airport Road" gets
   a deliberately coarser 120-min cadence.
3. **`seed_readings`** — ~35 days of gappy synthetic AQI. Each station has its
   own `gap_prob` (0.10 / 0.18 / 0.30 / 0.14) and station #2 gets a simulated
   **2-day total outage** 12–10 days ago. PM2.5 follows a diurnal curve with
   slow multi-day episode swings so the model sees both high and low regimes;
   pm10/no2 scale off it, o3 anti-correlates.
4. **`ingest_weather_synthetic(days=35)`**.
5. **`seed_user`** twice:
   - `demo@example.com` — 48 symptom logs over 25 days. Severity is generated as
     `0.6 + 0.05·PM2.5(t-24h) + 0.02·PM2.5(t-6h) + noise` — **this is the lag
     signal the model is supposed to recover.** ~40 % of logs carry a
     hand-typed (⇒ trusted) peak-flow value. Clears the personal-model
     threshold.
   - `new@example.com` — 4 logs over 3 days. Stays on the population fallback.
   Both passwords: `demo-pass-123`. Each user gets one `home` location with the
   nearest station resolved.
6. **`materialize_all(db)`** — build every user's exposure windows.
7. **`retrain_everything(db)`** — population fallback + a personal model per user.
8. **`write_metrics_doc(db)`** — regenerate `docs/METRICS.md` (best-effort;
   `OSError` swallowed if the path isn't writable).

`RNG = random.Random(20260828)` and a fixed `NOW` (truncated to the hour) make
the whole thing reproducible. Every `seed_*` function is idempotent (it looks up
by natural key before inserting), so re-running tops up rather than duplicating —
except symptom logs, which are appended each run.
