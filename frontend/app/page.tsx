import Link from "next/link";
import { Nav } from "@/components/Nav";

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

export default function Landing() {
  return (
    <div className="min-h-screen">
      <Nav />
      <main className="mx-auto max-w-6xl px-4 sm:px-6">
        <section className="relative py-20 sm:py-28">
          <div className="absolute inset-0 -z-10 bg-grid bg-[size:44px_44px] [mask-image:radial-gradient(40rem_30rem_at_50%_0%,black,transparent)]" />
          <p className="chip mx-auto w-fit">Next.js · FastAPI · PostgreSQL + pgvector · scikit-learn</p>
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
          <div className="mt-8 flex justify-center gap-3">
            <Link href="/register" className="btn-primary">
              Create an account
            </Link>
            <Link href="/login" className="btn-ghost">
              Sign in
            </Link>
          </div>
          <p className="mt-3 text-center text-xs text-slate-600">
            Seeded demo — <span className="font-mono text-slate-400">demo@example.com</span> /{" "}
            <span className="font-mono text-slate-400">demo-pass-123</span>
          </p>
        </section>

        <section className="grid gap-4 pb-24 sm:grid-cols-2 lg:grid-cols-3">
          {PRINCIPLES.map((p) => (
            <div key={p.k} className="card card-hover">
              <h3 className="text-sm font-semibold text-brand-soft">{p.k}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{p.d}</p>
            </div>
          ))}
        </section>
      </main>
      <footer className="border-t border-white/5 py-8 text-center text-xs text-slate-600">
        Portfolio project · models correlation with lagged features, not causation.
      </footer>
    </div>
  );
}
