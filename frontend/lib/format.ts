// WHO 2021 24-hour guideline reference values (µg/m³). Used ONLY for UI banding
// and the heuristic score — never as an authoritative claim (that's the RAG
// layer's job, with citations).
export const WHO_24H = { pm25: 15, pm10: 45, no2: 25, o3: 100 } as const;

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

export const bandLabel: Record<AqiBand, string> = {
  good: "Within WHO guideline",
  moderate: "Elevated",
  poor: "Unhealthy (sensitive groups)",
  bad: "Unhealthy",
  severe: "Hazardous",
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
