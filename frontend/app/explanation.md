# explanation.md — frontend/app/

App Router routes. `layout.tsx` wraps everything in `<AuthProvider>` and sets
metadata; `globals.css` holds the Tailwind layers and the utility classes
(`card`, `btn-primary`, `btn-ghost`, `chip`, `input`, `label`, `bg-grid`,
animations) that the components reference.

| Route | File | Type | What it is |
|---|---|---|---|
| `/` | `page.tsx` | Server | Landing page. Six principle cards (honest about gaps, lagged not same-day, personal + fallback, time-based eval, grounded advisory, correlation ≠ causation) + links to register / login. Shows the seeded demo credentials. |
| `/login` | `login/page.tsx` | Client | Email + password, pre-filled with `demo@example.com` / `demo-pass-123`. Calls `useAuth().login` → redirects to `/dashboard`. Shows `ApiError.detail` on failure. |
| `/register` | `register/page.tsx` | Client | Same shape; client-side 8-char minimum; `useAuth().register` (which registers then logs in). |
| `/dashboard` | `dashboard/page.tsx` | Client | The main screen. Redirects to `/login` if unauthenticated. |
| `/admin` | `admin/page.tsx` | Client | "Ingestion live feed" — proof the pipeline is live and that a silent station is logged, not a hole. |

## `dashboard/page.tsx`

Local state for locations / active location / windows / coverage / symptoms /
risk / models. On login: `loadLocations()` then `Promise.all` of
`/exposure/windows`, `/exposure/coverage-summary`, `/symptoms`, `/risk/score`,
`/risk/models`. `latest24h` is the most recent `24h` window for the active
location and feeds the gauge + stat pills.

Layout (grid): **row 1** current air quality (`AqiGauge` + `CoverageBadge` +
NO₂/O₃/PM10 pills) · `RiskCard` · `WhyThisScore`. **row 2** full-width
`TrendChart`. **row 3** `SymptomLogger` · `SymptomList` · `ModelScorecard`.
**row 4** `AdvisoryPanel` (2 cols) · `LiveAlerts`. **row 5** full-width data
coverage summary.

Exposure windows and models rebuild automatically as the background scheduler
ingests; the dashboard is read-only (there are no manual recompute/retrain
buttons). `/exposure/materialize` and `/risk/train` still exist on the API and
run from `Live feed → Run ingestion now` and the scheduler.

## `admin/page.tsx`

Fetches `/ingestion/stations` + `/ingestion/events`, and opens a WebSocket to
`/ws/admin-feed`. On each `tick` message it prepends to a rolling list of the
last 20 ticks and refreshes the tables. "Run ingestion now" → `POST
/ingestion/run`. The events table colour-codes `ok | gap | failure |
station_silent`. A live/offline dot reflects socket state.
