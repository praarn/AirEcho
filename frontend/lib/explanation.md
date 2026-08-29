# explanation.md — frontend/lib/

Non-UI plumbing: the API client, the auth context, formatting helpers, and the
TypeScript mirror of the backend's Pydantic schemas.

| File | Contents |
|---|---|
| `api.ts` | The typed `fetch` wrapper + token handling. |
| `auth.tsx` | `AuthProvider` / `useAuth()` React context. |
| `types.ts` | Hand-maintained interfaces matching `backend/app/schemas.py`. |
| `format.ts` | Banding, colours, number/time formatting, feature labels. |
| `clsx.ts` | 1-line `classnames` substitute. |

---

## `api.ts`

- Token storage: `localStorage` keys `aq.access` / `aq.refresh`
  (`getAccess` / `getRefresh` / `setTokens` / `clearTokens`). All guarded for SSR
  (`typeof window === "undefined"`).
- `url(path)` — prefixes `/api` unless the path is already absolute. In the
  browser `BASE` is `""` (same-origin, Next rewrites forward to the backend); on
  the server it's `NEXT_PUBLIC_API_BASE_URL`.
- `apiFetch<T>(path, init, { auth = true, retry })` — sets the bearer header and
  JSON content-type (skipped for `FormData`), throws `ApiError(status, detail)`
  on non-2xx (unwrapping FastAPI's `{detail}`), returns `undefined` for 204.
- **Transparent refresh:** on a 401 with auth, it calls `tryRefresh()` once and
  replays the request. `tryRefresh` memoises the in-flight promise so parallel
  401s trigger only one `/auth/refresh`; a failed refresh clears tokens.
- `wsUrl(path)` — builds `ws(s)://<api-host><path>?token=<access>` directly
  (WebSockets bypass the Next rewrite and can't send an auth header from the
  browser).

## `auth.tsx`

React context exposing `{ user, loading, login, register, logout }`.

- On mount, `refreshMe()` → `GET /auth/me` if an access token exists, else
  `user = null`.
- `login` → `POST /auth/login` (`auth:false`), store tokens, `refreshMe`, push
  `/dashboard`.
- `register` → `POST /auth/register` then `login`.
- `logout` → fire-and-forget `POST /auth/logout`, clear tokens, push `/login`.
- `useAuth()` throws if used outside `<AuthProvider>` (set in `app/layout.tsx`).

Route guarding is done in the page components, not here (`useEffect` →
`router.replace("/login")` when `!loading && !user`).

## `format.ts`

- `WHO_24H = { pm25: 15, pm10: 45, no2: 25, o3: 100 }` — **UI banding + the
  heuristic score only**, never presented as an authoritative claim (that's the
  RAG layer's job, with citations).
- `pm25Band` / `riskBand` → `good | moderate | poor | bad | severe`;
  `bandColor` / `bandLabel` map those to hex + text.
- `coverageTone(pct)` → `{label, color}`: ≥85 "high confidence", ≥60 "some gaps",
  ≥35 "gappy", else "very gappy — read with caution".
- `fmt(v, digits)` → localized number or `"—"` for null/NaN.
- `timeAgo(iso)` → `"5m ago"` etc.
- `featureLabel(feature)` → `"pm25_lag24"` → `"PM2.5 · t-24h"`,
  `"coverage_lag6"` → `"Coverage · t-6h"`.

## `types.ts`

Interfaces for every response shape the frontend consumes: `TokenPair`,
`UserOut`, `LocationOut`, `ExposureWindowOut`, `CoverageSummary`, `SymptomOut`,
`OcrResult`, `RiskPredictionOut` + `ExplanationItem`, `RiskModelOut`, `Citation`,
`AdvisoryOut`, `StationOut`, `IngestionEvent`. Kept in sync **by hand** with
`backend/app/schemas.py` — there is no codegen.
