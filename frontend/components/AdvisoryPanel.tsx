"use client";

import { useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import type { AdvisoryOut } from "@/lib/types";
import { Card, CardHeader, Spinner } from "./ui";

const SUGGESTIONS = [
  "Is it safe to run outside right now?",
  "What precautions apply at my current PM2.5 level?",
  "Which pollutant is the concern today?",
];

export function AdvisoryPanel({ locationId }: { locationId?: number }) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState<AdvisoryOut | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function ask(q: string) {
    setLoading(true);
    setErr(null);
    try {
      const out = await apiFetch<AdvisoryOut>("/advisory/ask", {
        method: "POST",
        body: JSON.stringify({ question: q || null, location_id: locationId ?? null }),
      });
      setRes(out);
    } catch (e) {
      setErr(e instanceof ApiError ? String(e.detail) : "Advisory failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Grounded advisory"
        hint="Rephrases only retrieved WHO / CPCB passages. Cites every claim. Refuses when the guidelines don't cover it."
      />

      <div className="flex gap-2">
        <input
          className="input"
          placeholder="Ask about your current exposure…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask(question)}
        />
        <button className="btn-primary shrink-0" disabled={loading} onClick={() => ask(question)}>
          {loading ? <Spinner /> : "Ask"}
        </button>
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => {
              setQuestion(s);
              ask(s);
            }}
            className="rounded-full border border-white/10 px-2.5 py-1 text-[11px] text-slate-400 transition hover:border-brand/30 hover:text-slate-100"
          >
            {s}
          </button>
        ))}
      </div>

      {err && <p className="mt-3 text-sm text-aq-bad">{err}</p>}

      {res && (
        <div className="mt-4 animate-fade-up">
          <div
            className={
              "rounded-xl border p-4 text-sm leading-relaxed " +
              (res.refused
                ? "border-amber-500/20 bg-amber-500/[0.06] text-amber-200/90"
                : "border-white/8 bg-white/[0.02] text-slate-200")
            }
          >
            {res.refused && (
              <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-amber-300/80">
                Refused — out of corpus
              </div>
            )}
            <p className="whitespace-pre-wrap">{res.response_text}</p>
          </div>

          {res.citations.length > 0 && (
            <ol className="mt-3 space-y-2">
              {res.citations.map((c) => (
                <li
                  key={c.marker}
                  className="rounded-lg border border-white/5 bg-white/[0.02] p-3 text-xs"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-brand-soft">
                      {c.marker} {c.section_ref}
                    </span>
                    <span className="tabular-nums text-slate-600">
                      sim {c.score.toFixed(2)}
                    </span>
                  </div>
                  <p className="mt-1 text-slate-400">{c.snippet}</p>
                  <p className="mt-1 text-[10px] uppercase tracking-wide text-slate-600">
                    {c.document_title}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </Card>
  );
}
