# explanation.md — backend/app/api/

The HTTP + WebSocket surface. Thin handlers: validate input, enforce per-user
isolation, delegate to `services/` / `ml/` / `rag/`, return a Pydantic model.

```
api/
├── deps.py          shared dependencies — auth + the isolation choke point
├── ws_manager.py    WebSocket connection registry + alert evaluation
└── routes/
    ├── auth.py        register / login / refresh / logout / me
    ├── locations.py   CRUD + nearest-station resolution
    ├── ingestion.py   admin/demo views of the live feed + manual tick
    ├── exposure.py    exposure windows + coverage summary + on-demand materialize
    ├── symptoms.py    symptom logs + peak-flow photo OCR + confirm-or-correct
    ├── risk.py        score / explain / models / train
    ├── advisory.py    grounded RAG advisory + history
    ├── privacy.py     full data export + hard delete
    └── ws.py          /ws/alerts (per-user) + /ws/admin-feed
```

---

## `deps.py` — the important one

- `current_user(token, db)` decodes the HS256 access token
  (`core/security.decode_access_token`), loads the `User`, or raises 401.
  Exposed as `CurrentUser = Annotated[User, Depends(current_user)]`.
- `DbDep = Annotated[Session, Depends(get_db)]`.
- **`scoped(db, model, user_id)`** → `select(model).where(model.user_id ==
  user_id)`. Every route that reads personal data starts from this and only adds
  `.where(...)` — it can never widen past the caller.
- **`get_owned_or_404(db, model, user_id, obj_id)`** → the row, or **404** (never
  403 — a 403 would confirm the id exists for someone else).

`tests/test_isolation.py` asserts user A gets 404 on every one of user B's
resources across every endpoint.

---

## Routes, briefly

### `auth.py`
`POST /auth/register` (409 on duplicate email) · `POST /auth/login` issues an
access JWT + an opaque refresh token · `POST /auth/refresh` **rotates**: the
presented refresh token is revoked and a new one minted; replaying a
rotated token revokes the whole user's chain (reuse detection, in
`core/security.rotate_refresh_token`) · `POST /auth/logout` revokes all refresh
tokens · `GET /auth/me`.

### `locations.py`
Create resolves the nearest station immediately (`services/geo.haversine_km`) and
**stores `distance_km`** — the UI shows "N km away", never hides the gap.
`POST /locations/{id}/resolve` re-runs it (a closer station may have come online).

### `ingestion.py` (all require auth; demo/admin flavour)
`GET /ingestion/stations` · `GET /ingestion/readings` (filter by station /
pollutant) · `GET /ingestion/events` — the `ok|gap|failure|station_silent` log ·
`POST /ingestion/run` triggers one `_tick_sync()` (ingest → materialize →
retrain) plus alert evaluation, synchronously, for demos.

### `exposure.py`
`GET /exposure/windows` (filter by `location_id`, `window_type ∈ {6h,24h,72h}`) ·
`GET /exposure/coverage-summary` (overall %, per-window-type %, worst window) ·
`POST /exposure/materialize?location_id=` recomputes now (409 if the location has
no resolved station).

### `symptoms.py`
`POST /symptoms` — a hand-typed entry; a typed `peak_flow_value` is
`manually_confirmed=True` (trusted). `POST /symptoms/ocr-preview` runs OCR on an
uploaded photo **without saving** (the confirm step UI). `POST
/symptoms/with-photo` saves the image under `uploads/`, stores the OCR value but
leaves it **unconfirmed** if low-confidence — excluded from every model/chart
until `POST /symptoms/{id}/confirm-peak-flow`. `_to_out` recomputes
`needs_confirmation` on read.

### `risk.py`
`GET /risk/score` predicts + persists a `risk_prediction`. `GET /risk/explain` —
same prediction, not persisted, plus ranked feature importances × current values
and the model disclaimer. `GET /risk/models` — this user's personal versions +
the shared population fallback. `POST /risk/train` — tries a personal retrain,
falls back to (and reports) the population model with the exact reason the
personal one was skipped.

### `advisory.py`
`POST /advisory/ask` builds a small context dict (latest 24h PM2.5 + coverage +
current risk score) and calls `rag/advisory.generate_advisory`. `GET
/advisory/history` returns past answers with citations.

### `privacy.py`
`GET /privacy/export` — one JSON dump of the caller's user row, locations,
symptoms, exposure windows, risk predictions and advisory log (writes an
`audit_log` row). `DELETE /privacy/delete` — hard-deletes all of it, revokes
every session, deletes the `users` row; the population fallback model
(`user_id IS NULL`) is untouched.

---

## `ws_manager.py` + `ws.py`

`ConnectionManager` keeps `{user_id: {sockets}}` and an admin socket set, guarded
by an asyncio lock. `evaluate_and_push_alerts()` runs after each scheduler tick
and pushes, **only to users with a live socket**:

- `threshold_alert` — latest PM2.5 at the user's station is above the WHO 24h
  reference (15 µg/m³).
- `risk_update` — the risk score moved ≥ 0.5 since the last push.

`ws.py` authenticates via a `?token=` query param (WebSockets can't send an
`Authorization` header from the browser), then on connect tells the client
*"fetch current state via REST, then resume"* — the socket is a push channel over
a REST source of truth, it never assumes it carried all state.
`tests/test_websocket.py` covers connect → threshold push → the reconnect
contract.
