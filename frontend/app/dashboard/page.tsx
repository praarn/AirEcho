"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  CoverageSummary,
  ExposureWindowOut,
  LocationOut,
  RiskModelOut,
  RiskPredictionOut,
  SymptomOut,
} from "@/lib/types";
import { Nav } from "@/components/Nav";
import { AqiGauge } from "@/components/AqiGauge";
import { RiskCard } from "@/components/RiskCard";
import { WhyThisScore } from "@/components/WhyThisScore";
import { TrendChart } from "@/components/TrendChart";
import { AdvisoryPanel } from "@/components/AdvisoryPanel";
import { SymptomLogger } from "@/components/SymptomLogger";
import { SymptomList } from "@/components/SymptomList";
import { ModelScorecard } from "@/components/ModelScorecard";
import { LiveAlerts } from "@/components/LiveAlerts";
import { LocationBar } from "@/components/LocationBar";
import { CoverageBadge } from "@/components/CoverageBadge";
import { Card, CardHeader, Spinner, StatPill } from "@/components/ui";
import { fmt, fmtIST } from "@/lib/format";

export default function Dashboard() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [locations, setLocations] = useState<LocationOut[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [windows, setWindows] = useState<ExposureWindowOut[]>([]);
  const [coverage, setCoverage] = useState<CoverageSummary | null>(null);
  const [symptoms, setSymptoms] = useState<SymptomOut[]>([]);
  const [risk, setRisk] = useState<RiskPredictionOut | null>(null);
  const [models, setModels] = useState<RiskModelOut[]>([]);
  const [ready, setReady] = useState(false);
  const [training, setTraining] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  const loadLocations = useCallback(async () => {
    const locs = await apiFetch<LocationOut[]>("/locations");
    setLocations(locs);
    setActiveId((cur) => cur ?? locs[0]?.id ?? null);
    return locs;
  }, []);

  const loadData = useCallback(async () => {
    const [w, cov, sym, r, m] = await Promise.all([
      apiFetch<ExposureWindowOut[]>("/exposure/windows"),
      apiFetch<CoverageSummary>("/exposure/coverage-summary"),
      apiFetch<SymptomOut[]>("/symptoms"),
      apiFetch<RiskPredictionOut>("/risk/score"),
      apiFetch<RiskModelOut[]>("/risk/models"),
    ]);
    setWindows(w);
    setCoverage(cov);
    setSymptoms(sym);
    setRisk(r);
    setModels(m);
  }, []);

  useEffect(() => {
    if (!user) return;
    (async () => {
      await loadLocations();
      await loadData().catch(() => {});
      setReady(true);
    })();
  }, [user, loadLocations, loadData]);

  const activeLoc = useMemo(
    () => locations.find((l) => l.id === activeId) ?? null,
    [locations, activeId],
  );

  const latest24h = useMemo(() => {
    const rows = windows
      .filter((w) => w.window_type === "24h" && (!activeId || w.location_id === activeId))
      .sort((a, b) => +new Date(b.window_end) - +new Date(a.window_end));
    return rows[0] ?? null;
  }, [windows, activeId]);

  async function materialize() {
    if (!activeId) return;
    await apiFetch(`/exposure/materialize?location_id=${activeId}`, { method: "POST" });
    await loadData();
  }

  async function retrain() {
    setTraining(true);
    try {
      await apiFetch("/risk/train", { method: "POST" });
      await loadData();
    } finally {
      setTraining(false);
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
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-white">Dashboard</h1>
            <p className="text-sm text-slate-500">
              {activeLoc
                ? `${activeLoc.label} · station #${activeLoc.nearest_station_id ?? "—"}`
                : "Add a location to begin"}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button className="btn-ghost !py-1.5 text-xs" onClick={materialize} disabled={!activeId}>
              Recompute windows
            </button>
            <button className="btn-ghost !py-1.5 text-xs" onClick={retrain} disabled={training}>
              {training ? <Spinner /> : "Retrain model"}
            </button>
          </div>
        </div>

        <div className="mt-4">
          <LocationBar
            locations={locations}
            activeId={activeId}
            onSelect={setActiveId}
            onChange={loadLocations}
          />
        </div>

        {!ready ? (
          <div className="grid place-items-center py-24">
            <Spinner className="h-6 w-6 text-brand" />
          </div>
        ) : (
          <div className="mt-6 grid gap-4 lg:grid-cols-3">
            {/* row 1 */}
            <Card>
              <CardHeader
                title="Current air quality"
                right={
                  latest24h ? (
                    <CoverageBadge
                      pct={latest24h.data_coverage_pct}
                      observed={latest24h.observed_slots}
                      expected={latest24h.expected_slots}
                    />
                  ) : undefined
                }
              />
              <AqiGauge
                pm25={latest24h?.avg_pm25 ?? null}
                distanceKm={activeLoc?.distance_km}
              />
              <div className="mt-4 grid grid-cols-3 gap-2">
                <StatPill label="NO₂ 24h" value={fmt(latest24h?.avg_no2)} sub="µg/m³" />
                <StatPill label="O₃ 24h" value={fmt(latest24h?.avg_o3)} sub="µg/m³" />
                <StatPill label="PM10 24h" value={fmt(latest24h?.avg_pm10)} sub="µg/m³" />
              </div>
            </Card>

            {risk && <RiskCard risk={risk} />}
            {risk && <WhyThisScore items={risk.explanation} />}

            {/* row 2 — full width */}
            <div className="lg:col-span-3">
              <TrendChart
                windows={windows.filter((w) => !activeId || w.location_id === activeId)}
                symptoms={symptoms}
              />
            </div>

            {/* row 3 */}
            <SymptomLogger onSaved={() => loadData()} />
            <SymptomList symptoms={symptoms} onChange={() => loadData()} />
            <ModelScorecard models={models} />

            {/* row 4 */}
            <div className="lg:col-span-2">
              <AdvisoryPanel locationId={activeId ?? undefined} />
            </div>
            <LiveAlerts />

            {coverage && (
              <div className="lg:col-span-3">
                <Card>
                  <CardHeader
                    title="Data coverage across your exposure windows"
                    hint="Ingestion gaps are visible, not hidden. Every number above inherits this."
                  />
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <StatPill
                      label="Overall"
                      value={`${fmt(coverage.overall_coverage_pct, 0)}%`}
                      sub={`${coverage.n_windows} windows`}
                    />
                    {Object.entries(coverage.by_window_type).map(([k, v]) => (
                      <StatPill key={k} label={`${k} windows`} value={`${fmt(v, 0)}%`} />
                    ))}
                  </div>
                  {coverage.worst_window && (
                    <p className="mt-3 text-xs text-slate-500">
                      Worst: {coverage.worst_window.window_type} window ending{" "}
                      {fmtIST(coverage.worst_window.window_end)} at{" "}
                      {fmt(coverage.worst_window.data_coverage_pct, 0)}% coverage (
                      {coverage.worst_window.observed_slots}/
                      {coverage.worst_window.expected_slots} readings).
                    </p>
                  )}
                </Card>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
