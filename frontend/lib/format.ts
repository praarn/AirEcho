// WHO 2021 24-hour guideline reference values (µg/m³). Used ONLY as a secondary
// UI reference — never as an authoritative claim (that's the RAG layer's job,
// with citations).
export const WHO_24H = { pm25: 15, pm10: 45, no2: 25, o3: 100 } as const;

// India's NAAQS 24-hour ambient standards (µg/m³) — the legal Indian limits.
export const NAAQS_24H = { pm25: 60, pm10: 100, no2: 80, o3: 100 } as const;

// ── CPCB National Air Quality Index (NAQI) ────────────────────────────────────
// The dashboard leads with the CPCB AQI because the modelled stations are in the
// Delhi-NCR airshed. Sub-index from the 24-hour PM2.5 concentration, using
// CPCB's published breakpoints, linearly interpolated within each band.
const CPCB_PM25_BREAKPOINTS: Array<[number, number, number, number]> = [
  // [Clo, Chi, Ilo, Ihi]
  [0, 30, 0, 50],
  [31, 60, 51, 100],
  [61, 90, 101, 200],
  [91, 120, 201, 300],
  [121, 250, 301, 400],
  [251, 500, 401, 500],
];

/** CPCB NAQI PM2.5 sub-index (0–500) from a 24-hour PM2.5 concentration. */
export function naqiFromPm25(pm25: number | null | undefined): number | null {
  if (pm25 == null || Number.isNaN(pm25)) return null;
  const c = Math.max(0, pm25);
  for (const [clo, chi, ilo, ihi] of CPCB_PM25_BREAKPOINTS) {
    if (c <= chi) return Math.round(((ihi - ilo) / (chi - clo)) * (c - clo) + ilo);
  }
  return 500;
}

export type NaqiKey =
  | "good"
  | "satisfactory"
  | "moderate"
  | "poor"
  | "very-poor"
  | "severe";

export interface NaqiCategory {
  key: NaqiKey;
  label: string;
  color: string;
  advice: string;
}

// Official CPCB category colours.
const NAQI_CATEGORIES: Array<{ max: number } & NaqiCategory> = [
  { max: 50, key: "good", label: "Good", color: "#55A84B", advice: "Air quality is fine. No precautions needed." },
  { max: 100, key: "satisfactory", label: "Satisfactory", color: "#A3C853", advice: "Minor discomfort possible for very sensitive people." },
  { max: 200, key: "moderate", label: "Moderate", color: "#F4C430", advice: "People with asthma or heart disease should limit prolonged outdoor exertion." },
  { max: 300, key: "poor", label: "Poor", color: "#F29C33", advice: "Cut back outdoor activity; sensitive groups should stay indoors when possible." },
  { max: 400, key: "very-poor", label: "Very Poor", color: "#E93F33", advice: "Avoid outdoor exertion. Mask up (N95) outdoors; run a purifier indoors." },
  { max: 999, key: "severe", label: "Severe", color: "#AF2D24", advice: "Everyone should avoid being outside. Keep windows shut; purifier on." },
];

export function naqiCategory(aqi: number | null | undefined): NaqiCategory {
  if (aqi == null || Number.isNaN(aqi)) {
    return { key: "moderate", label: "No data", color: "#94a3b8", advice: "Not enough recent readings to compute an index." };
  }
  const hit = NAQI_CATEGORIES.find((c) => aqi <= c.max) ?? NAQI_CATEGORIES[NAQI_CATEGORIES.length - 1];
  const { max: _max, ...rest } = hit;
  return rest;
}

/** GRAP stage triggered at a given CPCB AQI (Delhi-NCR). */
export function grapStage(aqi: number | null | undefined): string | null {
  if (aqi == null) return null;
  if (aqi >= 450) return "Stage IV";
  if (aqi >= 401) return "Stage III";
  if (aqi >= 301) return "Stage II";
  if (aqi >= 201) return "Stage I";
  return null;
}

export type AqiBand = "good" | "moderate" | "poor" | "bad" | "severe";

export function pm25Band(v: number | null | undefined): AqiBand {
  if (v == null) return "moderate";
  if (v <= 15) return "good";
  if (v <= 35) return "moderate";
  if (v <= 55) return "poor";
  if (v <= 150) return "bad";
  return "severe";
}

export const bandColor: Record<AqiBand, string> = {
  good: "#4ade80",
  moderate: "#facc15",
  poor: "#fb923c",
  bad: "#f87171",
  severe: "#c084fc",
};

// Labels for the predicted symptom-severity score (0–10), not for air quality.
export const bandLabel: Record<AqiBand, string> = {
  good: "Low",
  moderate: "Watch",
  poor: "Elevated",
  bad: "High",
  severe: "Very high",
};

export function riskBand(score: number): AqiBand {
  if (score < 2.5) return "good";
  if (score < 4.5) return "moderate";
  if (score < 6.5) return "poor";
  if (score < 8) return "bad";
  return "severe";
}

export function coverageTone(pct: number): { label: string; color: string } {
  if (pct >= 85) return { label: "high confidence", color: "#4ade80" };
  if (pct >= 60) return { label: "some gaps", color: "#facc15" };
  if (pct >= 35) return { label: "gappy", color: "#fb923c" };
  return { label: "very gappy — read with caution", color: "#f87171" };
}

export function fmt(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: digits });
}

// All modelled stations are in India — show wall-clock times in IST regardless
// of the viewer's timezone.
const IST = "Asia/Kolkata";

export function fmtIST(
  iso: string,
  opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" },
): string {
  return new Date(iso).toLocaleString("en-IN", { ...opts, timeZone: IST }) + " IST";
}

export function fmtDateIST(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: IST,
  });
}

export function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  const s = Math.round((Date.now() - then) / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

export function featureLabel(feature: string): string {
  const poll: Record<string, string> = { pm25: "PM2.5", pm10: "PM10", no2: "NO₂", o3: "O₃" };
  const m = feature.match(/^(pm25|pm10|no2|o3)_lag(\d+)$/);
  if (m) return `${poll[m[1]]} · t-${m[2]}h`;
  const c = feature.match(/^coverage_lag(\d+)$/);
  if (c) return `Coverage · t-${c[1]}h`;
  if (feature === "temp") return "Temperature";
  if (feature === "humidity") return "Humidity";
  return feature;
}
