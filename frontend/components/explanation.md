# explanation.md — frontend/components/

Presentational + lightly-stateful React components. All are `"use client"` except
the pure-display ones (`AqiGauge`, `RiskCard`, `WhyThisScore`, `ModelScorecard`,
parts of `ui`). Styling is Tailwind utility classes plus the custom classes in
`app/globals.css` (`card`, `btn-primary`, `chip`, `input`, `label`, …).

| Component | Role |
|---|---|
| `Nav.tsx` | Sticky header + the `Logo` SVG. Links to Dashboard / Live feed when signed in; shows the user email + "Sign out" (`useAuth().logout`). |
| `ui.tsx` | Primitives: `Card`, `CardHeader` (title + hint + right slot), `StatPill`, `Chip`, `Spinner`. Every other component composes these. |
| `LocationBar.tsx` | Pills for each saved location (with `distance_km` shown), plus an inline add form: label / lat / lng, a "use mine" button (`navigator.geolocation`). `POST /locations`, then `onChange()` re-fetches. |
| `AqiGauge.tsx` | Half-circle SVG gauge of current PM2.5, coloured by `pm25Band` (`lib/format`). Caption states the WHO 24h guideline (15 µg/m³) and the station distance. Pure display. |
| `CoverageBadge.tsx` | The pill shown next to **every** number derived from an exposure window — `NN% coverage`, coloured by `coverageTone`, tooltip `observed/expected readings`. This is how a gappy period visibly looks gappy. Ties to `exposure_windows.data_coverage_pct`. |
| `RiskCard.tsx` | The predicted-severity headline (0–10), band colour, a tag for `personal` / `population fallback` / `heuristic`, the algorithm + version chip, a `CoverageBadge`, and the model's own `disclaimer` string verbatim. |
| `WhyThisScore.tsx` | Horizontal bars of the top features by importance, each with its current value and a plain-language `reads_as` line. "Never a bare number." Data from `/risk/score`'s `explanation[]`. |
| `TrendChart.tsx` | Recharts `ComposedChart`: PM2.5 area + window-coverage bars + symptom-severity scatter + confirmed peak-flow line, on a shared time axis, with a 6h/24h/72h toggle. Merges `exposure_windows` and `symptoms` into one time-keyed row set. Labelled "Correlational, not causal." |
| `SymptomLogger.tsx` | Two-step logger. Step 1: severity slider + notes + optional typed peak flow → `POST /symptoms`. Photo path: `POST /symptoms/ocr-preview` (no save) → step 2 "confirm the reading" with the OCR value + confidence badge → `POST /symptoms/with-photo` then `POST /symptoms/{id}/confirm-peak-flow` with the confirmed/corrected value. |
| `SymptomList.tsx` | Recent entries. An unconfirmed OCR peak flow shows an amber **"unconfirmed — excluded from models"** badge and a "confirm / correct" inline editor (`POST /symptoms/{id}/confirm-peak-flow`); also delete. |
| `ModelScorecard.tsx` | Personal vs population-fallback **MAE** on the held-out future fold, vs the predict-the-mean baseline, with a Δ-vs-baseline metric ("beats predict-the-mean = learned something real"). Data from `/risk/models`. |
| `AdvisoryPanel.tsx` | Free-text question + 3 suggestion chips → `POST /advisory/ask`. Renders the answer, an amber "Refused — out of corpus" state when `refused`, and every citation as a card (`[n] section_ref`, similarity, snippet, document). |
| `LiveAlerts.tsx` | Opens `/ws/alerts` with exponential-backoff reconnect + a 25s ping. Renders `threshold_alert` (PM2.5 over the WHO guideline) and `risk_update` (score moved ≥ 0.5) messages. Header dot = connecting / live / offline. Comment notes the socket is a push channel over a REST source of truth. |

`lib/clsx.ts` is a 1-line `classnames` substitute used throughout.
