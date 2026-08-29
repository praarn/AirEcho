import type { Metadata } from "next";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { HeroCtas, SignedOut } from "@/components/Cta";

export const metadata: Metadata = {
  title: "Guide · AirEcho",
  description:
    "How to use AirEcho: add your locations anywhere in India, log symptoms, and read your lagged personal air-quality risk on the CPCB NAQI with CPCB-grounded advisory.",
};

const NAQI = [
  { band: "Good", range: "0–50", pm: "0–30", color: "#55A84B", note: "Minimal impact." },
  { band: "Satisfactory", range: "51–100", pm: "31–60", color: "#A3C853", note: "Minor discomfort to very sensitive people." },
  { band: "Moderate", range: "101–200", pm: "61–90", color: "#F4C430", note: "Asthma / heart patients limit prolonged exertion." },
  { band: "Poor", range: "201–300", pm: "91–120", color: "#F29C33", note: "Cut back outdoor activity (Delhi-NCR: GRAP I)." },
  { band: "Very Poor", range: "301–400", pm: "121–250", color: "#E93F33", note: "Mask up; purifier indoors (Delhi-NCR: GRAP II–III)." },
  { band: "Severe", range: "401–500", pm: "250+", color: "#AF2D24", note: "Stay indoors (Delhi-NCR: GRAP III–IV)." },
];

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-soft">
      <span className="h-px w-6 bg-brand/40" />
      {children}
    </div>
  );
}

function Section({
  id,
  eyebrow,
  title,
  children,
}: {
  id?: string;
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-20 border-t border-white/5 py-14 first:border-0">
      <Eyebrow>{eyebrow}</Eyebrow>
      <h2 className="text-2xl font-bold tracking-tight text-white">{title}</h2>
      <div className="mt-6 space-y-4 text-sm leading-relaxed text-slate-400">{children}</div>
    </section>
  );
}

function Step({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <div className="card">
      <div className="flex items-baseline gap-3">
        <span className="font-mono text-sm text-brand/70">{n}</span>
        <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-slate-400">{children}</p>
    </div>
  );
}

function Panel({ name, children }: { name: string; children: React.ReactNode }) {
  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-brand-soft">{name}</h3>
      <p className="mt-2 text-sm leading-relaxed text-slate-400">{children}</p>
    </div>
  );
}

function QA({ q, children }: { q: string; children: React.ReactNode }) {
  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-slate-100">{q}</h3>
      <p className="mt-2 text-sm leading-relaxed text-slate-400">{children}</p>
    </div>
  );
}

export default function GuidePage() {
  return (
    <div className="min-h-screen">
      <Nav />
      <main className="mx-auto max-w-4xl px-4 pb-24 sm:px-6">
        <header className="py-14">
          <Eyebrow>Guide</Eyebrow>
          <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            How to use AirEcho
          </h1>
          <p className="mt-4 max-w-2xl text-slate-400">
            AirEcho ties <span className="text-slate-200">your own</span> lagged exposure to{" "}
            <span className="text-slate-200">your own</span> respiratory symptoms for any
            location <span className="text-slate-200">in India</span> &mdash; a metro, a tier-2
            city, or a remote site like Leh or Port Blair. Air quality is reported on the{" "}
            <span className="text-slate-200">CPCB National Air Quality Index</span> (0–500),
            advisory text is grounded in CPCB (NAQI / NAAQS / GRAP) and WHO passages, and all
            times are shown in <span className="text-slate-200">IST</span>.
          </p>
          <div className="mt-6 flex flex-wrap gap-3 text-sm">
            <HeroCtas />
            <a href="#screens" className="btn-ghost">
              Jump to the screens
            </a>
          </div>
          <SignedOut>
            <p className="mt-3 text-xs text-slate-600">
              Try the seeded demo &mdash;{" "}
              <span className="font-mono text-slate-400">demo@example.com</span> /{" "}
              <span className="font-mono text-slate-400">demo-pass-123</span> (Kanpur +
              Bengaluru + Gangtok, personal model) or{" "}
              <span className="font-mono text-slate-400">new@example.com</span> (Port Blair,
              population fallback).
            </p>
          </SignedOut>
        </header>

        <Section eyebrow="Quick start" title="Five steps to a personal score">
          <div className="grid gap-4 sm:grid-cols-2">
            <Step n="01" title="Create an account">
              Email and a password (8+ characters). Your health data is isolated to your
              account and is exportable or deletable at any time.
            </Step>
            <Step n="02" title="Add one or more locations">
              On the dashboard, enter a label (Home, Office, Parents&rsquo;) and either type
              coordinates or use <span className="text-slate-300">&ldquo;use mine&rdquo;</span>.
              AirEcho snaps each location to the nearest CPCB / state-board monitoring station
              &mdash; anywhere in the country &mdash; and shows the distance.
            </Step>
            <Step n="03" title="Let ingestion run">
              A background scheduler pulls station readings and weather every few minutes. You
              can force a cycle from <span className="text-slate-300">Live feed → Run ingestion
              now</span>. Exposure windows and models rebuild automatically.
            </Step>
            <Step n="04" title="Log symptoms daily">
              Record a 0–10 severity whenever you notice something. Optionally attach a
              peak-flow meter photo &mdash; OCR reads the number and you confirm or correct it.
              Consistency matters more than volume.
            </Step>
            <Step n="05" title="Read your score and advisory">
              Once you have ~30 aligned logs over 2+ weeks, a personal model replaces the
              population fallback. The dashboard shows the predicted severity, which lagged
              features drove it, and a CPCB-grounded advisory you can question.
            </Step>
          </div>
        </Section>

        <Section id="screens" eyebrow="The screens" title="What each panel does">
          <p>
            <span className="font-semibold text-slate-200">Dashboard</span> &mdash; your daily
            view:
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <Panel name="Current air quality">
              The CPCB AQI (0–500) for your active location&rsquo;s nearest station, its
              category and colour, the raw PM2.5 against the NAAQS (60) and WHO (15) 24-hour
              references, and &mdash; for Delhi-NCR locations &mdash; the triggered GRAP stage.
            </Panel>
            <Panel name="Predicted symptom severity">
              A 0–10 estimate for the near term from the active model. The tag says whether
              it&rsquo;s <span className="text-slate-300">Personalized</span>, a{" "}
              <span className="text-slate-300">Population fallback</span>, or{" "}
              <span className="text-slate-300">Heuristic only</span>. The disclaimer is not
              boilerplate &mdash; read it.
            </Panel>
            <Panel name="Why this risk score">
              Feature importance from the active model &times; your current values, so the
              number is never bare. Entries like{" "}
              <span className="text-slate-300">PM2.5 · t-24h</span> mean exposure 24 hours
              before the predicted symptom.
            </Panel>
            <Panel name="Exposure &amp; symptom timeline">
              PM2.5 exposure windows with their data-coverage bars, plus symptom severity and
              confirmed peak-flow on the same axis. Toggle the range (7d / 30d / all) and the
              window length (6h / 24h / 72h).
            </Panel>
            <Panel name="Data coverage">
              Every exposure window stores <span className="font-mono text-slate-300">data_coverage_pct</span>{" "}
              &mdash; the share of expected station readings it actually saw. A gappy period
              looks gappy here and everywhere downstream; averages are never faked over holes.
            </Panel>
            <Panel name="Log a symptom">
              Severity slider, optional note, optional peak-flow value or meter photo. Photos
              go through OCR and land as <span className="text-slate-300">needs confirmation</span>{" "}
              until you accept the reading.
            </Panel>
            <Panel name="Recent symptoms">
              Your log history with peak-flow and confirmation state. Delete any entry; the
              model retrains without it.
            </Panel>
            <Panel name="Model scorecard">
              MAE on a held-out <span className="text-slate-300">future</span> fold (time-based
              split) for both your personal model and the population fallback, each against a
              predict-the-mean baseline. Beating the baseline is the signal that it learned
              something real.
            </Panel>
          </div>
          <p className="pt-2">
            <span className="font-semibold text-slate-200">Live feed</span> &mdash; proof the
            pipeline is alive: the tracked stations and when each was last seen, the ingestion
            event log (<span className="font-mono text-slate-300">ok · gap · failure ·
            station_silent</span>), the scheduler-tick history, a{" "}
            <span className="text-slate-300">Run ingestion now</span> button, and a socket-status
            pill. A silent station is logged as an event, never a quiet hole in the data.
          </p>
        </Section>

        <Section eyebrow="Concepts" title="The ideas behind the numbers">
          <div className="space-y-4">
            <Panel name="Exposure windows &amp; coverage">
              Raw station readings, weather and your symptom logs are aligned into fixed 6h /
              24h / 72h windows per location. Each window records how complete its data was.
              This is the honest core of the project.
            </Panel>
            <Panel name="Lagged features, not same-day">
              Features are pollutant and weather exposure at t-0, t-6h, t-24h and t-72h{" "}
              <span className="text-slate-300">before</span> each symptom. The model predicts
              from the past, never from same-day co-occurrence.
            </Panel>
            <Panel name="Personal model vs population fallback">
              A RandomForest is trained just for you once you clear the minimum-data threshold
              (~30 feature-complete logs spanning 2+ weeks). Until then you get a model trained
              on anonymized pooled data, labelled &ldquo;general pattern, not yet personalized
              to you.&rdquo;
            </Panel>
            <Panel name="Time-based evaluation only">
              Never a random split. No future row is allowed into training. Reported error is
              against a held-out future fold, so it reflects how the model would have done
              predicting forward.
            </Panel>
            <Panel name="Grounded advisory">
              The advisory box only rephrases retrieved CPCB (NAQI / NAAQS / GRAP) and WHO
              passages, with inline <span className="font-mono text-slate-300">[1] [2]</span>{" "}
              citations. Any number it can&rsquo;t trace to a passage is dropped, and questions
              the corpus doesn&rsquo;t cover are refused rather than guessed.
            </Panel>
            <Panel name="OCR confirm-or-correct">
              Peak-flow photos are read with Tesseract. Low-confidence reads are flagged; you
              always get the final say before the value is used.
            </Panel>
          </div>
        </Section>

        <Section eyebrow="India reference" title="CPCB National Air Quality Index">
          <p>
            The dashboard leads with the CPCB AQI &mdash; the same national 0–500 index CPCB
            publishes for cities across India. The overall AQI is the worst pollutant
            sub-index; AirEcho computes the PM2.5 sub-index from CPCB&rsquo;s 24-hour
            breakpoints.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] border-collapse text-left text-xs">
              <thead>
                <tr className="text-slate-500">
                  <th className="border-b border-white/10 py-2 pr-4 font-medium">Category</th>
                  <th className="border-b border-white/10 py-2 pr-4 font-medium">AQI</th>
                  <th className="border-b border-white/10 py-2 pr-4 font-medium">PM2.5 24-h (µg/m³)</th>
                  <th className="border-b border-white/10 py-2 font-medium">What it means</th>
                </tr>
              </thead>
              <tbody>
                {NAQI.map((r) => (
                  <tr key={r.band} className="align-top">
                    <td className="border-b border-white/5 py-2 pr-4">
                      <span className="inline-flex items-center gap-2 font-medium text-slate-200">
                        <span
                          className="h-2.5 w-2.5 rounded-full"
                          style={{ backgroundColor: r.color }}
                        />
                        {r.band}
                      </span>
                    </td>
                    <td className="border-b border-white/5 py-2 pr-4 font-mono text-slate-400">
                      {r.range}
                    </td>
                    <td className="border-b border-white/5 py-2 pr-4 font-mono text-slate-400">
                      {r.pm}
                    </td>
                    <td className="border-b border-white/5 py-2 text-slate-400">{r.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="pt-2">
            <span className="font-semibold text-slate-200">Regional variation:</span> the
            Indo-Gangetic Plain (Delhi, Kanpur, Lucknow, Patna) records the country&rsquo;s
            highest PM2.5, worst from late October to January &mdash; inversion, low wind,
            paddy-stubble smoke, Diwali firecrackers. Peninsular metros sit mid-range;
            Himalayan, north-eastern and island stations (Leh, Gangtok, Itanagar, Port Blair)
            are usually Good–Satisfactory year-round. The synthetic history follows each
            region&rsquo;s climatology, so what you see depends on the location and the month
            you seed.
          </p>
          <p>
            <span className="font-semibold text-slate-200">GRAP</span> (Graded Response Action
            Plan) is a <span className="text-slate-300">Delhi-NCR-specific</span> escalation:
            Stage I at AQI 201, II at 301, III at 401, IV at 450. AirEcho only shows a GRAP
            stage for NCR locations; other cities have their own local action plans.
          </p>
        </Section>

        <Section eyebrow="Privacy" title="Your data, your call">
          <p>
            Per-user isolation is enforced in the query layer, not trusted from request
            parameters. <span className="font-mono text-slate-300">GET /privacy/export</span>{" "}
            returns a full JSON dump of your health data;{" "}
            <span className="font-mono text-slate-300">DELETE /privacy/delete</span>{" "}
            hard-deletes it and revokes every refresh token. Population-model training drops
            your <span className="font-mono text-slate-300">user_id</span> before the data
            reaches the trainer.
          </p>
        </Section>

        <Section eyebrow="FAQ" title="Common questions">
          <div className="grid gap-4 sm:grid-cols-2">
            <QA q="Why does my score say &ldquo;Heuristic only&rdquo;?">
              No model has trained yet &mdash; usually you just added your first location and
              ingestion hasn&rsquo;t produced enough windows. It&rsquo;s a rule-of-thumb read
              of current PM2.5 against the WHO 24-hour guideline so the dashboard isn&rsquo;t
              empty.
            </QA>
            <QA q="Why did the advisory refuse to answer?">
              The retrieved CPCB / WHO passages didn&rsquo;t match your question closely enough
              to cite. That&rsquo;s deliberate &mdash; the system refuses rather than letting
              the model improvise a threshold.
            </QA>
            <QA q="Why is my data coverage low?">
              The station near that location reported intermittently in the window, or was
              silent. Check <span className="text-slate-300">Live feed</span> for{" "}
              <span className="font-mono text-slate-300">gap</span> /{" "}
              <span className="font-mono text-slate-300">station_silent</span> events. Low
              coverage is surfaced, not smoothed away.
            </QA>
            <QA q="Is this medical advice?">
              No. AirEcho models a <span className="text-slate-300">correlation</span> between
              self-reported severity and lagged exposure in a small, noisy sample. It is not
              causal and not a substitute for a clinician.
            </QA>
            <QA q="How often should I log?">
              Once a day is plenty; more when symptoms change. The personal model needs ~30
              feature-complete logs over 2+ weeks before it takes over.
            </QA>
            <QA q="Can I track more than one place?">
              Yes. Add as many locations as you like and switch the active one from the
              location bar; each resolves to its own nearest station.
            </QA>
          </div>
        </Section>

        <div className="mt-8 flex flex-wrap gap-3 text-sm">
          <SignedOut>
            <Link href="/register" className="btn-primary">
              Create an account
            </Link>
          </SignedOut>
          <Link href="/dashboard" className="btn-ghost">
            Go to the dashboard
          </Link>
          <Link href="/" className="btn-ghost">
            Back to home
          </Link>
        </div>
      </main>
    </div>
  );
}
