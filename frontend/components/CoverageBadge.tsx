import { coverageTone, fmt } from "@/lib/format";

/**
 * Data-coverage indicator. Appears next to every number derived from an
 * exposure window so a gappy period visibly looks gappy — ties directly to
 * `exposure_windows.data_coverage_pct`.
 */
export function CoverageBadge({
  pct,
  observed,
  expected,
  size = "sm",
}: {
  pct: number;
  observed?: number;
  expected?: number;
  size?: "sm" | "md";
}) {
  const tone = coverageTone(pct);
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium"
      style={{ borderColor: `${tone.color}44`, color: tone.color }}
      title={
        observed != null && expected != null
          ? `${observed} of ${expected} expected readings present — ${tone.label}`
          : tone.label
      }
    >
      <span className="relative flex h-1.5 w-1.5">
        <span
          className="absolute inline-flex h-full w-full rounded-full opacity-60"
          style={{ backgroundColor: tone.color }}
        />
      </span>
      {fmt(pct, 0)}% coverage
      {size === "md" && <span className="text-slate-500">· {tone.label}</span>}
    </span>
  );
}
