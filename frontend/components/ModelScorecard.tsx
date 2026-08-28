import type { RiskModelOut } from "@/lib/types";
import { fmt } from "@/lib/format";
import { Card, CardHeader } from "./ui";

/**
 * Personal vs population-fallback MAE, against a predict-the-mean baseline.
 * "The personalized model actually outperforms the generic one" is a real,
 * checkable claim — this is where it's checked.
 */
export function ModelScorecard({ models }: { models: RiskModelOut[] }) {
  const active = models.filter(
    (m) => m.algorithm === "random_forest" && m.mae != null,
  );
  const personal = active.find((m) => m.model_type === "personal");
  const population = active.find((m) => m.model_type === "population_fallback");

  const rows = [
    personal && { label: "Your personal model", m: personal, tone: "#4ade80" },
    population && { label: "Population fallback", m: population, tone: "#facc15" },
  ].filter(Boolean) as { label: string; m: RiskModelOut; tone: string }[];

  return (
    <Card>
      <CardHeader
        title="Model scorecard"
        hint="MAE on a held-out future fold (time-based split). Lower is better; beats predict-the-mean = learned something real."
      />
      {rows.length === 0 ? (
        <p className="py-4 text-sm text-slate-600">No trained models yet.</p>
      ) : (
        <div className="space-y-3">
          {rows.map(({ label, m, tone }) => {
            const beatsBy =
              m.baseline_mae != null && m.mae != null ? m.baseline_mae - m.mae : null;
            return (
              <div key={m.id} className="rounded-xl border border-white/5 bg-white/[0.02] p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-200">{label}</span>
                  <span
                    className="rounded-full px-2 py-0.5 text-[11px] font-semibold"
                    style={{ backgroundColor: `${tone}1f`, color: tone }}
                  >
                    v{m.model_version}
                  </span>
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-center">
                  <Metric k="MAE" v={fmt(m.mae, 2)} />
                  <Metric k="baseline" v={fmt(m.baseline_mae, 2)} />
                  <Metric
                    k="Δ vs baseline"
                    v={beatsBy != null ? `${beatsBy >= 0 ? "−" : "+"}${fmt(Math.abs(beatsBy), 2)}` : "—"}
                    good={beatsBy != null && beatsBy > 0}
                  />
                </div>
                <p className="mt-2 text-[11px] text-slate-500">
                  train {m.n_train} · test {m.n_test} · trained{" "}
                  {new Date(m.trained_at).toLocaleDateString()}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

function Metric({ k, v, good }: { k: string; v: string; good?: boolean }) {
  return (
    <div>
      <div className="label">{k}</div>
      <div
        className="mt-0.5 text-sm font-semibold tabular-nums"
        style={{ color: good ? "#4ade80" : undefined }}
      >
        {v}
      </div>
    </div>
  );
}
