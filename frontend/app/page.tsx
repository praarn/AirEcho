import Link from "next/link";
import { Nav } from "@/components/Nav";

const REPO_URL = "https://github.com/praarn/AirEcho";

const STATS = [
  { v: "3", l: "irregular series aligned" },
  { v: "4", l: "lag horizons (t-0 · 6h · 24h · 72h)" },
  { v: "6h / 24h / 72h", l: "exposure windows" },
  { v: "WHO + CPCB", l: "grounded advisory corpus" },
];

const STEPS = [
  {
    n: "01",
    k: "Align",
    d: "Raw sensor readings, daily weather and symptom logs collapse into fixed 6h / 24h / 72h exposure windows. Each window records data_coverage_pct — the share of expected sensor slots it actually saw — so a gappy period visibly looks gappy.",
  },
  {
    n: "02",
    k: "Lag the features",
    d: "Features are pollutant and weather exposure at t-0, t-6h, t-24h and t-72h before each symptom. The model predicts near-term severity from the past, never from same-day co-occurrence.",
  },
  {
    n: "03",
    k: "Personalise, with a fallback",
    d: "A RandomForest per user once there are 30+ aligned logs across 2+ weeks. Until then, a clearly-labelled population model trained on anonymized pooled data. Evaluation is always a time-based split — no future row leaks into training.",
  },
  {
    n: "04",
    k: "Advise from citations",
    d: "Advisory text only rephrases retrieved WHO / CPCB guideline passages, with inline [1] [2] citations. Anything it can't trace to a chunk is dropped; out-of-corpus questions are refused rather than guessed.",
  },
];

const PRINCIPLES = [
  {
    k: "Honest about gaps",
    d: "Every exposure window stores data_coverage_pct from real reporting gaps. A rolling average is never computed as if a sensor didn't go quiet — and the coverage number travels all the way to the chart.",
  },
  {
    k: "Lagged, not same-day",
    d: "Features are exposure at t-0, t-6h, t-24h and t-72h feeding one prediction of near-term symptom severity. Modeling the lag is the whole point.",
  },
  {
    k: "Personal, with a real fallback",
    d: "A RandomForest per user once there are 30+ aligned logs across 2+ weeks; a clearly-labelled population model trained on anonymized data until then.",
  },
  {
    k: "Time-based evaluation only",
    d: "Never a random split. Tests assert no future row leaks into training. MAE is reported against a held-out future fold and a predict-the-mean baseline.",
  },
  {
    k: "Grounded advisory",
    d: "The LLM may only rephrase retrieved WHO / CPCB passages, with inline citations. Any number it can't trace to a chunk is discarded; out-of-corpus questions are refused.",
  },
  {
    k: "Correlation, not causation",
    d: "Self-reported severity against lagged exposure is small-sample and noisy. Nothing in the UI overclaims — saying so is the stronger engineering signal.",
  },
];

const STACK = [
  "Next.js 15",
  "TypeScript",
  "Tailwind CSS",
  "Recharts",
  "FastAPI",
  "Pydantic v2",
  "SQLAlchemy 2.0",
  "PostgreSQL + pgvector",
  "scikit-learn",
  "sentence-transformers",
  "Tesseract OCR",
  "Docker Compose",
];

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-soft">
      <span className="h-px w-6 bg-brand/40" />
      {children}
    </div>
  );
}

export default function Landing() {
  return (
    <div className="min-h-screen">
      <Nav />
      <main className="mx-auto max-w-6xl px-4 sm:px-6">
        {/* Hero */}
        <section className="relative py-20 sm:py-28">
          <div className="absolute inset-0 -z-10 bg-grid bg-[size:44px_44px] [mask-image:radial-gradient(40rem_30rem_at_50%_0%,black,transparent)]" />
          <div className="animate-fade-up">
            <div className="mx-auto flex w-fit items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-slate-400">
              <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-brand" />
              Air-Quality Health Risk Correlator
            </div>
            <h1 className="mx-auto mt-5 max-w-3xl text-center text-4xl font-bold leading-[1.1] tracking-tight text-white sm:text-6xl">
              Today&apos;s air echoes into{" "}
              <span className="bg-gradient-to-r from-brand-soft to-fuchsia-400 bg-clip-text text-transparent">
                how you feel tomorrow
              </span>
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-center text-lg text-slate-400">
              Generic AQI apps show everyone the same number. AirEcho aligns three irregular
              time series — sensors, weather, and whenever you happen to log a symptom — into a
              feature space a lagged model can actually learn from, without pretending the data
              is cleaner than it is.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Link href="/register" className="btn-primary">
                Create an account
              </Link>
              <Link href="/login" className="btn-ghost">
                Sign in
              </Link>
              <a href="#about" className="btn-ghost">
                What is this?
              </a>
            </div>
            <p className="mt-3 text-center text-xs text-slate-600">
              Seeded demo — <span className="font-mono text-slate-400">demo@example.com</span> /{" "}
              <span className="font-mono text-slate-400">demo-pass-123</span>
            </p>
          </div>
        </section>

        {/* Stats strip */}
        <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {STATS.map((s) => (
            <div
              key={s.l}
              className="rounded-2xl border border-white/5 bg-ink-850/60 px-4 py-4 text-center backdrop-blur-sm"
            >
              <div className="text-lg font-semibold text-white">{s.v}</div>
              <div className="mt-1 text-[11px] leading-tight text-slate-500">{s.l}</div>
            </div>
          ))}
        </section>

        {/* About */}
        <section id="about" className="scroll-mt-20 py-20 sm:py-28">
          <div className="grid gap-10 lg:grid-cols-[1fr_1.1fr] lg:items-start lg:gap-16">
            <div>
              <Eyebrow>About</Eyebrow>
              <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
                A personal model, built to stay honest about its data
              </h2>
              <p className="mt-4 text-sm leading-relaxed text-slate-400">
                A person logs their respiratory symptoms — a 0–10 severity, optionally a
                peak-flow meter photo read by OCR. In the background AirEcho pulls air-quality
                readings for a station near that person plus daily weather, then ties
                <span className="text-slate-200"> their own lagged exposure history to their
                own symptom pattern</span>.
              </p>
              <p className="mt-3 text-sm leading-relaxed text-slate-400">
                The hard part is aligning three genuinely irregular time series — sensor
                readings on their own polling cadence, weather on another, and symptoms logged
                whenever the user happens to log them — into one feature space a model can
                learn from, without ever pretending the data is cleaner or more complete than
                it is.
              </p>
              <div className="mt-6 flex flex-wrap gap-3 text-sm">
                <a href={REPO_URL} target="_blank" rel="noreferrer" className="btn-ghost">
                  Source on GitHub
                </a>
                <a href="#how" className="btn-ghost">
                  How it works
                </a>
              </div>
            </div>

            <div className="card self-start border-brand/15 bg-ink-850/80">
              <div className="label">Honest scoping note — read this</div>
              <p className="mt-3 text-sm leading-relaxed text-slate-300">
                Self-reported symptom severity correlated with lagged pollutant exposure is
                exactly that: <span className="text-white">correlational</span>, small-sample,
                and noisy. This is <span className="text-white">not causal inference</span>, and
                nothing in the UI or the API claims otherwise.
              </p>
              <p className="mt-3 text-sm leading-relaxed text-slate-400">
                The value of the project is the honesty of the pipeline: explicit data-coverage
                accounting, time-based splits, a population fallback for thin-history users, and
                a RAG layer that refuses rather than guesses.
              </p>
              <div className="mt-5 grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-white/5 bg-white/[0.02] p-3">
                  <div className="text-sm font-semibold text-brand-soft">Per-user isolation</div>
                  <div className="mt-1 text-[11px] leading-tight text-slate-500">
                    Enforced in the query layer, never trusted from request params.
                  </div>
                </div>
                <div className="rounded-xl border border-white/5 bg-white/[0.02] p-3">
                  <div className="text-sm font-semibold text-brand-soft">Export &amp; delete</div>
                  <div className="mt-1 text-[11px] leading-tight text-slate-500">
                    Full JSON dump on request; hard-delete revokes every refresh token.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* How it works */}
        <section id="how" className="scroll-mt-20 border-t border-white/5 py-20 sm:py-28">
          <Eyebrow>How it works</Eyebrow>
          <h2 className="max-w-2xl text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Four steps from raw, gappy readings to a cited advisory
          </h2>
          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            {STEPS.map((s) => (
              <div key={s.n} className="card card-hover">
                <div className="flex items-baseline gap-3">
                  <span className="font-mono text-sm text-brand/70">{s.n}</span>
                  <h3 className="text-sm font-semibold text-slate-100">{s.k}</h3>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">{s.d}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Principles */}
        <section id="principles" className="scroll-mt-20 border-t border-white/5 py-20 sm:py-28">
          <Eyebrow>Principles</Eyebrow>
          <h2 className="max-w-2xl text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Six commitments the code actually keeps
          </h2>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {PRINCIPLES.map((p, i) => (
              <div key={p.k} className="card card-hover">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-slate-600">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <h3 className="text-sm font-semibold text-brand-soft">{p.k}</h3>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">{p.d}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Stack */}
        <section className="border-t border-white/5 py-20 sm:py-24">
          <Eyebrow>Built with</Eyebrow>
          <div className="mt-4 flex flex-wrap gap-2">
            {STACK.map((t) => (
              <span key={t} className="chip">
                {t}
              </span>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t border-white/5 py-10">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 px-4 text-center text-xs text-slate-600 sm:px-6">
          <p>Portfolio project · models correlation with lagged features, not causation.</p>
          <div className="flex items-center gap-4">
            <a
              href={REPO_URL}
              target="_blank"
              rel="noreferrer"
              className="text-slate-500 transition hover:text-slate-300"
            >
              GitHub
            </a>
            <a href="#about" className="text-slate-500 transition hover:text-slate-300">
              About
            </a>
            <Link href="/login" className="text-slate-500 transition hover:text-slate-300">
              Sign in
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
