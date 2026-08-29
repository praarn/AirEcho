# explanation.md — frontend/

Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, Recharts. No state
library, no data-fetching library — a small typed `fetch` wrapper and one React
context.

```
frontend/
├── app/          ← explanation.md — routes: landing, login, register, dashboard, admin
├── components/   ← explanation.md — dashboard widgets (gauge, risk card, charts, …)
├── lib/          ← explanation.md — api.ts (fetch + token refresh), auth.tsx, format.ts, types.ts
├── next.config.mjs   rewrites /api/* and /uploads/* → the backend
├── tailwind.config.ts / postcss.config.mjs / app/globals.css
└── Dockerfile        multi-stage: deps → build → run (next start)
```

---

## How it talks to the backend

`next.config.mjs` rewrites:

```
/api/:path*     → ${NEXT_PUBLIC_API_BASE_URL}/:path*      (default http://localhost:8000)
/uploads/:path* → ${NEXT_PUBLIC_API_BASE_URL}/uploads/:path*
```

So the browser only ever calls same-origin `/api/...`; `lib/api.ts` prefixes
paths with `/api`. WebSockets can't go through the rewrite, so `wsUrl()` builds a
direct `ws(s)://<api-host>/ws/...?token=<access>` URL.

## Auth model

Tokens live in `localStorage` (`aq.access`, `aq.refresh`). `lib/auth.tsx`
provides `AuthProvider` / `useAuth()` with `user`, `loading`, `login`,
`register`, `logout`. On mount it calls `/auth/me` if an access token exists.
`lib/api.ts::apiFetch` transparently retries once on a 401 after rotating the
refresh token (concurrent 401s share one in-flight refresh promise).

Route protection is client-side: `dashboard` and `admin` `useEffect(() =>
router.replace("/login"))` when `!loading && !user`.

## Rendering

- `app/page.tsx` (landing) and `app/layout.tsx` are Server Components.
- Everything interactive (`dashboard`, `admin`, `login`, `register`, all
  components with hooks) is `"use client"`.
- The dashboard fetches on the client: `loadLocations()` then a `Promise.all` of
  `/exposure/windows`, `/exposure/coverage-summary`, `/symptoms`, `/risk/score`,
  `/risk/models`, and re-runs `loadData()` after any mutation.

## Commands

```powershell
npm install            # first time (CI: npm ci)
npm run dev            # http://localhost:3000
npm run build          # production build — CI expects "Compiled successfully"
npm run start          # serve the build
npm run typecheck      # tsc --noEmit
npm run lint           # next lint
```

`NEXT_PUBLIC_API_BASE_URL` is the only env var; unset ⇒ `http://localhost:8000`.
