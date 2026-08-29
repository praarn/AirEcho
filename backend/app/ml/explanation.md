# explanation.md — backend/app/ml/

Lagged risk modelling — predict *near-term symptom severity* from exposure at
several points in the **past**, not from same-day co-occurrence. Not a black box:
interpretable baseline kept alongside, time-based evaluation only, feature
importances exposed.

```
ml/
├── config.py     every constant + WHY it has that value (interview talking points)
├── features.py   lag-feature construction (CORE #2)
├── train.py      fit LinearRegression + RandomForest, time-split, persist, version
├── predict.py    pick best model, build current row, predict, explain
└── artifacts/    joblib payloads: personal_u<id>_v<n>.joblib, population_v<n>.joblib
```

---

## `config.py` — the numbers, and their reasons

| Constant | Value | Why |
|---|---|---|
| `LAG_HOURS` | `(0, 6, 24, 72)` | Each feature is mean exposure over a 6h sub-window ending `lag` hours before the symptom. Modelling the lag *is* the project. |
| `SUBWINDOW_HOURS` | `6` | Width of every lag sub-window. |
| `POLLUTANTS` | `pm25, pm10, no2, o3` | |
| `MIN_T0_COVERAGE_PCT` | `1.0` | A row whose t-0 window saw **zero** data is dropped — no exposure signal. Low-but-nonzero coverage is kept; the `coverage_lag*` feature lets the model discount it. |
| `MIN_PERSONAL_SAMPLES` | `30` | Enough aligned logs for a time-split to leave a non-trivial test fold and for a forest to see each lag/pollutant combo more than once. |
| `MIN_PERSONAL_DAYS` | `14` | 30 logs from one week describe one pollution episode, not a personal pattern. Two weeks can contain a high *and* a low regime. |
| `MIN_POPULATION_SAMPLES` | `40` | Floor before a population model is trained at all. |
| `TEST_FRACTION` | `0.25` | Held-out **future** fold. |
| `RF_PARAMS` | 200 trees, `max_depth=6`, `min_samples_leaf=3` | Small and shallow on purpose — with noisy self-reports a deep forest just memorises. |

Also three disclaimer strings (`DISCLAIMER_PERSONAL / _POPULATION / _HEURISTIC`)
that the API returns verbatim so the UI never has to invent its own hedging.

---

## `features.py` — CORE #2

`feature_names()` → for each lag: `pm25_lag{L}, pm10_lag{L}, no2_lag{L},
o3_lag{L}, coverage_lag{L}`, then `temp, humidity` (from the t-0 sub-window).
`coverage_lag*` is a **real feature**, not bookkeeping — it lets the model learn
to trust a lag less when the sensor was quiet.

`build_feature_row(db, station, symptom_time, readings?, weather?)` — for a
symptom at time `t`, for each lag `L`: anchor `= t - L`, sub-window
`[anchor-6h, anchor)`, and it **reuses
`exposure_pipeline.compute_exposure_window()`** to get the pollutant means and
the coverage of that sub-window. `readings`/`weather` can be pre-fetched wider to
avoid a query per log.

`build_training_frame(db, user_id)` — one feature-complete row per symptom log
for the user's primary resolved location; drops rows with `coverage_lag0 <
MIN_T0_COVERAGE_PCT`; columns = `feature_names() + severity + logged_at`.

`aggregate_training_frame(db)` — concatenates `build_training_frame` for **every**
user, sorted by time. **Privacy:** no `user_id` column is ever added; there's an
in-function `assert "user_id" not in pooled.columns` and
`tests/test_risk_model.py` asserts it too.

`time_based_split(frame, test_fraction)` — chronological slice, **never random**.
A random split leaks the future into training and inflates the score.

---

## `train.py`

Per model: build frame → gate on thresholds → `time_based_split` → `_fit_and_score`:

- **LinearRegression** in a `StandardScaler` pipeline — interpretable baseline,
  coefficients stored, predictions clipped to `[0,10]`.
- **RandomForestRegressor** (`RF_PARAMS`) — the served model.
- **predict-the-mean baseline MAE** — the "did we beat trivial?" number.
- Feature importances (RF) and coefficients (linear) rounded and stored as JSON.

`train_personal(db, user_id)` returns `TrainOutcome(trained=False, reason=...)`
with the exact shortfall (`"below personal threshold: 12/30 feature-complete
logs, 9.4/14 day span"`) when under threshold — the caller then serves the
population fallback. `train_population(db)` trains on the anonymized pooled frame.

Each successful train: `_deactivate_previous` the same `(user_id, model_type)`,
write a `linear_regression` row (kept for the metrics story, `is_active=False`)
and a `random_forest` row (`is_active=True`), bump `model_version`, and dump a
joblib payload `{"rf", "linear", "features"}` to `artifacts/`.

`retrain_everything(db)` — population first, then every user; called by the
scheduler and the seed. `write_metrics_doc(db)` regenerates `docs/METRICS.md`.

`tests/test_risk_model.py` asserts `max(train.logged_at) <= min(test.logged_at)`,
the threshold gate, and frame anonymization.

---

## `predict.py`

`_active_model(db, user_id)` selection order:

1. active **personal** RandomForest (user cleared the threshold),
2. active **population-fallback** RandomForest,
3. **heuristic** — `2.0 + 4.0 * (pm25_now / 15)` clipped to `[0,10]`, algorithm
   `who_pm25_ratio`, version 0, explicitly labelled *"No trained model yet …
   rule-of-thumb"* so it's never mistaken for a model output.

`predict_for_user(db, user_id, persist=True)` builds the current lag row
(anchored at now), loads the joblib payload, predicts, clips to `[0,10]`, and
returns `risk_score`, `model_type`, `is_personalized`, the matching disclaimer,
the full `lag_features`, an `explanation` (top-6 features by importance ×
current value, each with a human-readable `reads_as`), and
`data_coverage_pct` (the t-0 coverage). When `persist`, a `risk_predictions` row
is written. Also used by the WebSocket alert evaluator with `persist=False`.
