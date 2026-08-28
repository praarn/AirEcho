"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import type { LocationOut } from "@/lib/types";
import { fmt } from "@/lib/format";
import { clsx } from "@/lib/clsx";
import { Spinner } from "./ui";

export function LocationBar({
  locations,
  activeId,
  onSelect,
  onChange,
}: {
  locations: LocationOut[];
  activeId: number | null;
  onSelect: (id: number) => void;
  onChange: () => void;
}) {
  const [adding, setAdding] = useState(locations.length === 0);
  const [label, setLabel] = useState("home");
  const [lat, setLat] = useState("");
  const [lng, setLng] = useState("");
  const [busy, setBusy] = useState(false);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await apiFetch("/locations", {
        method: "POST",
        body: JSON.stringify({ label, lat: Number(lat), lng: Number(lng) }),
      });
      setAdding(false);
      setLat("");
      setLng("");
      onChange();
    } finally {
      setBusy(false);
    }
  }

  function useMyLocation() {
    navigator.geolocation?.getCurrentPosition((pos) => {
      setLat(pos.coords.latitude.toFixed(4));
      setLng(pos.coords.longitude.toFixed(4));
    });
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {locations.map((l) => (
        <button
          key={l.id}
          onClick={() => onSelect(l.id)}
          className={clsx(
            "rounded-xl border px-3 py-1.5 text-sm transition",
            activeId === l.id
              ? "border-brand/40 bg-brand/10 text-white"
              : "border-white/10 bg-white/[0.02] text-slate-400 hover:text-slate-100",
          )}
        >
          {l.label}
          {l.distance_km != null && (
            <span className="ml-1.5 text-[11px] text-slate-500">{fmt(l.distance_km, 1)} km</span>
          )}
        </button>
      ))}

      {!adding ? (
        <button className="btn-ghost !py-1.5 text-sm" onClick={() => setAdding(true)}>
          + Location
        </button>
      ) : (
        <form onSubmit={add} className="flex flex-wrap items-center gap-2">
          <input
            className="input !w-28 !py-1.5"
            placeholder="label"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
          <input
            className="input !w-24 !py-1.5"
            placeholder="lat"
            value={lat}
            onChange={(e) => setLat(e.target.value)}
            required
          />
          <input
            className="input !w-24 !py-1.5"
            placeholder="lng"
            value={lng}
            onChange={(e) => setLng(e.target.value)}
            required
          />
          <button type="button" className="btn-ghost !py-1.5 text-xs" onClick={useMyLocation}>
            use mine
          </button>
          <button className="btn-primary !py-1.5 text-sm" disabled={busy}>
            {busy ? <Spinner /> : "Add"}
          </button>
          {locations.length > 0 && (
            <button
              type="button"
              className="text-xs text-slate-600 hover:text-slate-300"
              onClick={() => setAdding(false)}
            >
              cancel
            </button>
          )}
        </form>
      )}
    </div>
  );
}
