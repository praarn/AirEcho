"use client";

import { useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { OcrResult, SymptomOut } from "@/lib/types";
import { clsx } from "@/lib/clsx";
import { Card, CardHeader, Spinner } from "./ui";

type Step = "form" | "confirm";

export function SymptomLogger({ onSaved }: { onSaved: (s: SymptomOut) => void }) {
  const [severity, setSeverity] = useState(3);
  const [notes, setNotes] = useState("");
  const [peakFlow, setPeakFlow] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [step, setStep] = useState<Step>("form");
  const [ocr, setOcr] = useState<OcrResult | null>(null);
  const [ocrValue, setOcrValue] = useState<string>("");
  const fileRef = useRef<File | null>(null);

  async function submitText() {
    setBusy(true);
    setMsg(null);
    try {
      const body: Record<string, unknown> = { severity, notes: notes || null };
      if (peakFlow) body.peak_flow_value = Number(peakFlow);
      const s = await apiFetch<SymptomOut>("/symptoms", {
        method: "POST",
        body: JSON.stringify(body),
      });
      onSaved(s);
      setNotes("");
      setPeakFlow("");
      setSeverity(3);
      setMsg("Logged.");
    } finally {
      setBusy(false);
    }
  }

  async function runOcr(file: File) {
    fileRef.current = file;
    setBusy(true);
    setMsg(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await apiFetch<OcrResult>("/symptoms/ocr-preview", { method: "POST", body: fd });
      setOcr(r);
      setOcrValue(r.extracted_value != null ? String(r.extracted_value) : "");
      setStep("confirm");
    } finally {
      setBusy(false);
    }
  }

  async function saveWithPhoto() {
    if (!fileRef.current) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", fileRef.current);
      fd.append("severity", String(severity));
      if (notes) fd.append("notes", notes);
      const s = await apiFetch<SymptomOut>("/symptoms/with-photo", { method: "POST", body: fd });
      // apply the user's confirmed/corrected value
      const finalVal = Number(ocrValue);
      if (!Number.isNaN(finalVal) && (s.needs_confirmation || s.peak_flow_value !== finalVal)) {
        const fixed = await apiFetch<SymptomOut>(`/symptoms/${s.id}/confirm-peak-flow`, {
          method: "POST",
          body: JSON.stringify({ peak_flow_value: finalVal }),
        });
        onSaved(fixed);
      } else {
        onSaved(s);
      }
      setStep("form");
      setOcr(null);
      setNotes("");
      setSeverity(3);
      setMsg("Logged with peak-flow photo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader title="Log a symptom" hint="Severity now; optional peak-flow meter photo with OCR confirm-or-correct." />

      <label className="label">Severity — {severity}/10</label>
      <input
        type="range"
        min={0}
        max={10}
        value={severity}
        onChange={(e) => setSeverity(Number(e.target.value))}
        className="mt-1 w-full accent-brand"
      />
      <div className="mt-1 flex justify-between text-[10px] text-slate-600">
        <span>none</span>
        <span>severe</span>
      </div>

      <textarea
        className="input mt-3 min-h-[64px] resize-y"
        placeholder="Notes (optional) — e.g. tight chest on the walk in"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
      />

      {step === "form" && (
        <>
          <div className="mt-3 flex gap-2">
            <input
              className="input"
              inputMode="decimal"
              placeholder="Peak flow (L/min), if you have it"
              value={peakFlow}
              onChange={(e) => setPeakFlow(e.target.value)}
            />
          </div>

          <div className="mt-3 flex items-center gap-2">
            <button className="btn-primary flex-1" disabled={busy} onClick={submitText}>
              {busy ? <Spinner /> : "Save entry"}
            </button>
            <label className="btn-ghost cursor-pointer">
              📷 Photo
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && runOcr(e.target.files[0])}
              />
            </label>
          </div>
        </>
      )}

      {step === "confirm" && ocr && (
        <div className="mt-4 animate-fade-up rounded-xl border border-white/8 bg-white/[0.02] p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-slate-100">Confirm the reading</span>
            <span
              className={clsx(
                "rounded-full px-2 py-0.5 text-[11px] font-medium",
                ocr.needs_confirmation
                  ? "bg-amber-500/15 text-amber-300"
                  : "bg-emerald-500/15 text-emerald-300",
              )}
            >
              {ocr.engine} · {(ocr.confidence * 100).toFixed(0)}% conf
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {ocr.needs_confirmation
              ? "Low confidence — this value will not be used in any model or chart until you confirm it."
              : "Looks clear. Adjust if the meter shows something different."}
          </p>
          <input
            className="input mt-3"
            inputMode="decimal"
            value={ocrValue}
            onChange={(e) => setOcrValue(e.target.value)}
            placeholder="Enter the peak-flow value"
          />
          <div className="mt-3 flex gap-2">
            <button
              className="btn-primary flex-1"
              disabled={busy || !ocrValue}
              onClick={saveWithPhoto}
            >
              {busy ? <Spinner /> : "Confirm & save"}
            </button>
            <button className="btn-ghost" onClick={() => setStep("form")}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {msg && <p className="mt-2 text-xs text-emerald-400">{msg}</p>}
    </Card>
  );
}
