import {
  fmt,
  grapStage,
  isNcrStation,
  naqiCategory,
  naqiFromPm25,
  NAAQS_24H,
  WHO_24H,
} from "@/lib/format";

export function AqiGauge({
  pm25,
  station,
  distanceKm,
}: {
  pm25: number | null;
  station?: string | null;
  distanceKm?: number | null;
}) {
  const aqi = naqiFromPm25(pm25);
  const cat = naqiCategory(aqi);
  const color = cat.color;
  const max = 500; // CPCB NAQI scale
  const pct = Math.max(0, Math.min(1, (aqi ?? 0) / max));
  const R = 82;
  const C = Math.PI * R; // half circle
  const dash = C * pct;
  const grap = isNcrStation(station) ? grapStage(aqi) : null;

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 200 120" className="w-full max-w-[260px]">
        <path
          d="M16 108 A82 82 0 0 1 184 108"
          fill="none"
          stroke="rgba(148,163,184,0.15)"
          strokeWidth="14"
          strokeLinecap="round"
        />
        <path
          d="M16 108 A82 82 0 0 1 184 108"
          fill="none"
          stroke={color}
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${C}`}
          style={{ transition: "stroke-dasharray 0.8s ease" }}
        />
        <text
          x="100"
          y="84"
          textAnchor="middle"
          className="fill-slate-100"
          fontSize="32"
          fontWeight="700"
        >
          {aqi == null ? "—" : aqi}
        </text>
        <text x="100" y="103" textAnchor="middle" className="fill-slate-500" fontSize="11">
          CPCB AQI
        </text>
      </svg>
      <div
        className="mt-1 rounded-full px-3 py-1 text-xs font-semibold"
        style={{ backgroundColor: `${color}1f`, color }}
      >
        {cat.label}
        {grap ? ` · GRAP ${grap}` : ""}
      </div>
      <p className="mt-2 max-w-[260px] text-center text-[11px] leading-relaxed text-slate-500">
        PM2.5 {fmt(pm25, 0)} µg/m³ · NAAQS 24-h {NAAQS_24H.pm25} · WHO 24-h {WHO_24H.pm25}
        {station ? ` · ${station}` : ""}
        {distanceKm != null ? ` · ${fmt(distanceKm, 1)} km away` : ""}
      </p>
      <p className="mt-1.5 max-w-[260px] text-center text-[11px] leading-relaxed text-slate-400">
        {cat.advice}
      </p>
    </div>
  );
}
