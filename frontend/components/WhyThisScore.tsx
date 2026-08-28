import type { ExplanationItem } from "@/lib/types";
import { featureLabel } from "@/lib/format";
import { Card, CardHeader } from "./ui";

export function WhyThisScore({ items }: { items: ExplanationItem[] }) {
  const max = Math.max(...items.map((i) => i.importance), 0.0001);

  return (
    <Card>
      <CardHeader
        title="Why this risk score"
        hint="Feature importance from the active model × your current values — never a bare number."
      />
      <ul className="space-y-3">
        {items.map((it) => (
          <li key={it.feature}>
            <div className="flex items-baseline justify-between text-xs">
              <span className="font-medium text-slate-200">{featureLabel(it.feature)}</span>
              <span className="tabular-nums text-slate-500">
                now {it.current_value}
                {it.feature.startsWith("coverage") ? "%" : ""}
              </span>
            </div>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-white/[0.04]">
              <div
                className="h-full rounded-full bg-gradient-to-r from-brand-deep to-brand-soft"
                style={{ width: `${(it.importance / max) * 100}%` }}
              />
            </div>
            <p className="mt-1 text-[11px] text-slate-500">{it.reads_as}</p>
          </li>
        ))}
      </ul>
    </Card>
  );
}
