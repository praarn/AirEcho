import { bandColor, bandLabel, fmt, pm25Band, WHO_24H } from "@/lib/format";

export function AqiGauge({
  pm25,
  station,
  distanceKm,
}: {
  pm25: number | null;
  station?: string | null;
  distanceKm?: number | null;
}) {
  const band = pm25Band(pm25);
  const color = bandColor[band];
  const max = 150;
  const pct = Math.max(0, Math.min(1, (pm25 ?? 0) / max));
  const R = 78;
  const C = Math.PI * R; // half circle
  const dash = C * pct;

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
        <text x="100" y="86" textAnchor="middle" className="fill-slate-100" fontSize="30" fontWeight="700">
          {fmt(pm25, 0)}
        </text>
        <text x="100" y="104" textAnchor="middle" className="fill-slate-500" fontSize="11">
          µg/m³ PM2.5
        </text>
      </svg>
      <div
        className="mt-1 rounded-full px-3 py-1 text-xs font-semibold"
        style={{ backgroundColor: `${color}1f`, color }}
      >
        {bandLabel[band]}
      </div>
      <p className="mt-2 text-center text-[11px] text-slate-500">
        WHO 24-h guideline {WHO_24H.pm25} µg/m³
        {station ? ` · ${station}` : ""}
        {distanceKm != null ? ` · ${fmt(distanceKm, 1)} km away` : ""}
      </p>
    </div>
  );
}
