import type { RiskPredictionOut } from "@/lib/types";
import { bandColor, bandLabel, fmt, riskBand } from "@/lib/format";
import { CoverageBadge } from "./CoverageBadge";
import { Card } from "./ui";

export function RiskCard({ risk }: { risk: RiskPredictionOut }) {
  const band = riskBand(risk.risk_score);
  const color = bandColor[band];

  const modelTag =
    risk.model_type === "personal"
      ? { text: "Personalized", tone: "#4ade80" }
      : risk.model_type === "population_fallback"
        ? { text: "Population fallback", tone: "#facc15" }
        : { text: "Heuristic only", tone: "#94a3b8" };

  return (
    <Card className="relative overflow-hidden" hover>
      <div
        className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full blur-3xl"
        style={{ backgroundColor: `${color}22` }}
      />
      <div className="flex items-start justify-between">
        <div>
          <div className="label">Predicted symptom severity</div>
          <div className="mt-1 flex items-end gap-2">
            <span className="text-5xl font-bold tracking-tight" style={{ color }}>
              {fmt(risk.risk_score, 1)}
            </span>
            <span className="pb-1 text-sm text-slate-500">/ 10</span>
          </div>
          <div className="mt-1 text-sm font-medium" style={{ color }}>
            {bandLabel[band]}
          </div>
        </div>
        <span
          className="rounded-full px-2.5 py-1 text-[11px] font-semibold"
          style={{ backgroundColor: `${modelTag.tone}1f`, color: modelTag.tone }}
        >
          {modelTag.text}
        </span>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="chip">
          {risk.algorithm.replace(/_/g, " ")} · v{risk.model_version}
        </span>
        {risk.data_coverage_pct != null && (
          <CoverageBadge pct={risk.data_coverage_pct} />
        )}
      </div>

      <p className="mt-3 rounded-lg border border-white/5 bg-white/[0.02] p-3 text-[12px] leading-relaxed text-slate-400">
        {risk.disclaimer}
      </p>
    </Card>
  );
}
