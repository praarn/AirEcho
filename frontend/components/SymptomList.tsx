"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import type { SymptomOut } from "@/lib/types";
import { bandColor, riskBand, timeAgo } from "@/lib/format";
import { Card, CardHeader } from "./ui";

export function SymptomList({
  symptoms,
  onChange,
}: {
  symptoms: SymptomOut[];
  onChange: () => void;
}) {
  const [editing, setEditing] = useState<number | null>(null);
  const [val, setVal] = useState("");

  async function confirm(id: number) {
    await apiFetch(`/symptoms/${id}/confirm-peak-flow`, {
      method: "POST",
      body: JSON.stringify({ peak_flow_value: Number(val) }),
    });
    setEditing(null);
    onChange();
  }

  async function remove(id: number) {
    await apiFetch(`/symptoms/${id}`, { method: "DELETE" });
    onChange();
  }

  return (
    <Card>
      <CardHeader title="Recent symptoms" hint={`${symptoms.length} entries`} />
      {symptoms.length === 0 ? (
        <p className="py-4 text-sm text-slate-600">Nothing logged yet.</p>
      ) : (
        <ul className="max-h-[420px] space-y-2 overflow-y-auto scrollbar-thin pr-1">
          {symptoms.map((s) => {
            const c = bandColor[riskBand(s.severity)];
            return (
              <li
                key={s.id}
                className="rounded-lg border border-white/5 bg-white/[0.02] p-3 text-sm"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span
                      className="grid h-7 w-7 place-items-center rounded-lg text-xs font-bold"
                      style={{ backgroundColor: `${c}22`, color: c }}
                    >
                      {s.severity}
                    </span>
                    <span className="text-slate-300">{s.notes || "—"}</span>
                  </div>
                  <span className="text-[11px] text-slate-600">{timeAgo(s.logged_at)}</span>
                </div>

                {s.peak_flow_value != null && (
                  <div className="mt-2 flex items-center gap-2 text-xs">
                    <span className="text-slate-400">peak flow {s.peak_flow_value} L/min</span>
                    {s.needs_confirmation ? (
                      <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-medium text-amber-300">
                        unconfirmed — excluded from models
                      </span>
                    ) : (
                      <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
                        confirmed
                      </span>
                    )}
                  </div>
                )}

                {editing === s.id ? (
                  <div className="mt-2 flex gap-2">
                    <input
                      className="input !py-1.5"
                      inputMode="decimal"
                      placeholder="corrected value"
                      value={val}
                      onChange={(e) => setVal(e.target.value)}
                    />
                    <button className="btn-primary !py-1.5" onClick={() => confirm(s.id)}>
                      Save
                    </button>
                  </div>
                ) : (
                  <div className="mt-2 flex gap-3 text-[11px]">
                    {s.needs_confirmation && (
                      <button
                        className="text-brand hover:underline"
                        onClick={() => {
                          setEditing(s.id);
                          setVal(String(s.peak_flow_value ?? ""));
                        }}
                      >
                        confirm / correct
                      </button>
                    )}
                    <button
                      className="text-slate-600 hover:text-aq-bad"
                      onClick={() => remove(s.id)}
                    >
                      delete
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
