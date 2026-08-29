"use client";

import { useMemo, useState } from "react";
import {
  Area,
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ExposureWindowOut, SymptomOut } from "@/lib/types";
import { clsx } from "@/lib/clsx";
import { fmt, fmtIST } from "@/lib/format";
import { Card, CardHeader } from "./ui";

type Row = {
  t: number;
  label: string;
  pm25?: number | null;
  coverage?: number | null;
  severity?: number | null;
  peak?: number | null;
};

const WINDOWS = ["6h", "24h", "72h"] as const;
const RANGES = { "7d": 7, "30d": 30, all: Infinity } as const;

export function TrendChart({
  windows,
  symptoms,
}: {
  windows: ExposureWindowOut[];
  symptoms: SymptomOut[];
}) {
  const [wt, setWt] = useState<(typeof WINDOWS)[number]>("24h");
  const [range, setRange] = useState<keyof typeof RANGES>("30d");

  const data = useMemo<Row[]>(() => {
    const cutoff =
      RANGES[range] === Infinity ? -Infinity : Date.now() - RANGES[range] * 86_400_000;
    const lbl = (t: number) =>
      fmtIST(new Date(t).toISOString(), { month: "short", day: "numeric", hour: "2-digit" });
    const byT = new Map<number, Row>();
    for (const w of windows.filter((w) => w.window_type === wt)) {
      const t = new Date(w.window_end).getTime();
      if (t < cutoff) continue;
      byT.set(t, { t, label: lbl(t), pm25: w.avg_pm25, coverage: w.data_coverage_pct });
    }
    for (const s of symptoms) {
      const t = new Date(s.logged_at).getTime();
      if (t < cutoff) continue;
      const existing = byT.get(t) ?? { t, label: lbl(t) };
      existing.severity = s.severity;
      existing.peak = s.manually_confirmed ? s.peak_flow_value : null;
      byT.set(t, existing);
    }
    return [...byT.values()].sort((a, b) => a.t - b.t);
  }, [windows, symptoms, wt, range]);

  const empty = data.length === 0;

  return (
    <Card>
      <CardHeader
        title="Exposure & symptom timeline"
        hint="PM2.5 exposure windows with data coverage, symptom severity on the same axis. Correlational, not causal."
        right={
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex rounded-lg border border-white/10 bg-white/[0.02] p-0.5">
              {(Object.keys(RANGES) as Array<keyof typeof RANGES>).map((r) => (
                <button
                  key={r}
                  onClick={() => setRange(r)}
                  className={clsx(
                    "rounded-md px-2.5 py-1 text-xs font-medium transition",
                    range === r ? "bg-white/10 text-white" : "text-slate-400 hover:text-slate-100",
                  )}
                >
                  {r}
                </button>
              ))}
            </div>
            <div className="flex rounded-lg border border-white/10 bg-white/[0.02] p-0.5">
              {WINDOWS.map((w) => (
                <button
                  key={w}
                  onClick={() => setWt(w)}
                  className={clsx(
                    "rounded-md px-2.5 py-1 text-xs font-medium transition",
                    wt === w ? "bg-brand text-ink-950" : "text-slate-400 hover:text-slate-100",
                  )}
                >
                  {w}
                </button>
              ))}
            </div>
          </div>
        }
      />
      {empty ? (
        <div className="flex h-64 items-center justify-center text-sm text-slate-600">
          Nothing in this range — widen it, or add a location and let ingestion run.
        </div>
      ) : (
        <div className="h-72 w-full">
          <ResponsiveContainer>
            <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
              <defs>
                <linearGradient id="pm" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#38bdf8" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(148,163,184,0.08)" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fill: "#64748b", fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                minTickGap={28}
              />
              <YAxis
                yAxisId="pm"
                tick={{ fill: "#64748b", fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                label={{ value: "PM2.5", angle: -90, position: "insideLeft", fill: "#475569", fontSize: 10 }}
              />
              <YAxis
                yAxisId="sev"
                orientation="right"
                domain={[0, 10]}
                tick={{ fill: "#64748b", fontSize: 10 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                contentStyle={{
                  background: "#0f1620",
                  border: "1px solid rgba(148,163,184,0.15)",
                  borderRadius: 12,
                  fontSize: 12,
                }}
                labelStyle={{ color: "#94a3b8" }}
                formatter={(v: number | string, name: string) => {
                  if (name === "coverage") return [`${fmt(Number(v), 0)}%`, "coverage"];
                  if (name === "pm25") return [`${fmt(Number(v), 1)} µg/m³`, "PM2.5"];
                  if (name === "severity") return [v, "severity"];
                  if (name === "peak") return [`${v} L/min`, "peak flow"];
                  return [v, name];
                }}
              />
              <Bar yAxisId="sev" dataKey="coverage" name="coverage" fill="rgba(74,222,128,0.10)" barSize={10} />
              <Area
                yAxisId="pm"
                type="monotone"
                dataKey="pm25"
                name="pm25"
                stroke="#38bdf8"
                strokeWidth={2}
                fill="url(#pm)"
                connectNulls
              />
              <Scatter yAxisId="sev" dataKey="severity" name="severity" fill="#f87171" />
              <Line
                yAxisId="sev"
                type="monotone"
                dataKey="peak"
                name="peak"
                stroke="#c084fc"
                strokeWidth={1.5}
                dot={{ r: 2 }}
                connectNulls
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-slate-500">
        <Legend color="#38bdf8" label="PM2.5 exposure" />
        <Legend color="#f87171" label="Symptom severity" />
        <Legend color="#c084fc" label="Peak flow (confirmed)" />
        <Legend color="rgba(74,222,128,0.5)" label="Window data coverage" />
      </div>
    </Card>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}
