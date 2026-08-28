"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, wsUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { IngestionEvent, StationOut } from "@/lib/types";
import { Nav } from "@/components/Nav";
import { Card, CardHeader, Spinner } from "@/components/ui";
import { timeAgo } from "@/lib/format";

const STATUS_TONE: Record<string, string> = {
  ok: "#4ade80",
  gap: "#facc15",
  failure: "#f87171",
  station_silent: "#fb923c",
};

export default function AdminFeed() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [stations, setStations] = useState<StationOut[]>([]);
  const [events, setEvents] = useState<IngestionEvent[]>([]);
  const [ticks, setTicks] = useState<Record<string, unknown>[]>([]);
  const [live, setLive] = useState(false);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  const load = useCallback(async () => {
    const [s, e] = await Promise.all([
      apiFetch<StationOut[]>("/ingestion/stations"),
      apiFetch<IngestionEvent[]>("/ingestion/events"),
    ]);
    setStations(s);
    setEvents(e);
  }, []);

  useEffect(() => {
    if (user) load().catch(() => {});
  }, [user, load]);

  const wsRef = useRef<WebSocket | null>(null);
  useEffect(() => {
    if (!user) return;
    const ws = new WebSocket(wsUrl("/ws/admin-feed"));
    wsRef.current = ws;
    ws.onopen = () => setLive(true);
    ws.onclose = () => setLive(false);
    ws.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data);
        if (m.type === "tick") {
          setTicks((t) => [m, ...t].slice(0, 20));
          load().catch(() => {});
        }
      } catch {
        /* ignore */
      }
    };
    return () => ws.close();
  }, [user, load]);

  async function runOnce() {
    setRunning(true);
    try {
      await apiFetch("/ingestion/run", { method: "POST" });
      await load();
    } finally {
      setRunning(false);
    }
  }

  if (loading || !user) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Spinner className="h-6 w-6 text-brand" />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <Nav />
      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-white">Ingestion live feed</h1>
            <p className="text-sm text-slate-500">
              Proof the pipeline is live — and that a silent station is logged, not a hole.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="chip">
              <span
                className={
                  "h-1.5 w-1.5 rounded-full " +
                  (live ? "animate-pulse-dot bg-emerald-400" : "bg-slate-500")
                }
              />
              {live ? "socket live" : "offline"}
            </span>
            <button className="btn-primary !py-1.5 text-xs" onClick={runOnce} disabled={running}>
              {running ? <Spinner /> : "Run ingestion now"}
            </button>
          </div>
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader title="Stations" hint={`${stations.length} tracked`} />
            <ul className="space-y-2">
              {stations.map((s) => (
                <li
                  key={s.id}
                  className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.02] p-3 text-sm"
                >
                  <div>
                    <div className="text-slate-200">{s.location_name}</div>
                    <div className="text-[11px] text-slate-500">
                      {s.source} · every {s.nominal_cadence_minutes} min ·{" "}
                      {s.lat.toFixed(3)}, {s.lng.toFixed(3)}
                    </div>
                  </div>
                  <span className="text-[11px] text-slate-500">
                    {s.last_seen_at ? timeAgo(s.last_seen_at) : "never"}
                  </span>
                </li>
              ))}
            </ul>
          </Card>

          <Card>
            <CardHeader title="Scheduler ticks" hint="each ingestion → materialize → retrain cycle" />
            {ticks.length === 0 ? (
              <p className="py-4 text-sm text-slate-600">
                Waiting for the next tick (or hit “Run ingestion now”).
              </p>
            ) : (
              <ul className="space-y-2">
                {ticks.map((t, i) => (
                  <li key={i} className="rounded-lg border border-white/5 bg-white/[0.02] p-3 text-sm animate-fade-up">
                    <span className="text-slate-200">
                      +{String(t.aqi_rows)} readings · {String(t.windows)} windows
                    </span>
                    <span className="ml-2 text-[11px] text-slate-500">
                      alerts {JSON.stringify(t.alerts)} · {timeAgo(String(t.at))}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <div className="lg:col-span-2">
            <Card>
              <CardHeader title="Ingestion events" hint="ok · gap · failure · station_silent" />
              <div className="max-h-[420px] overflow-y-auto scrollbar-thin">
                <table className="w-full text-sm">
                  <thead className="text-[11px] uppercase tracking-wide text-slate-600">
                    <tr className="border-b border-white/5">
                      <th className="py-2 text-left">status</th>
                      <th className="py-2 text-left">source</th>
                      <th className="py-2 text-left">station</th>
                      <th className="py-2 text-left">detail</th>
                      <th className="py-2 text-right">rows</th>
                      <th className="py-2 text-right">when</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((e) => (
                      <tr key={e.id} className="border-b border-white/5">
                        <td className="py-2">
                          <span
                            className="rounded-full px-2 py-0.5 text-[11px] font-medium"
                            style={{
                              backgroundColor: `${STATUS_TONE[e.status] ?? "#94a3b8"}1f`,
                              color: STATUS_TONE[e.status] ?? "#94a3b8",
                            }}
                          >
                            {e.status}
                          </span>
                        </td>
                        <td className="py-2 text-slate-400">{e.source}</td>
                        <td className="py-2 text-slate-400">{e.station_id ?? "—"}</td>
                        <td className="py-2 text-slate-500">{e.detail}</td>
                        <td className="py-2 text-right tabular-nums text-slate-400">
                          {e.rows_ingested}
                        </td>
                        <td className="py-2 text-right text-[11px] text-slate-600">
                          {timeAgo(e.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
