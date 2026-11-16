import Link from "next/link";

import Term from "@/components/Term";
import type { AssessResponse } from "@/lib/api";
import {
  BREAKDOWN_LABELS, CONFIDENCE, VERDICT, gbp, gbpRange, kwh, paybackNote, years,
} from "@/lib/format";
import { ROUTE_PATHS, stepHref, withRoute } from "@/lib/journey";

// ── 1. Verdict ────────────────────────────────────────────────────────────────

export function VerdictCard({ data }: { data: AssessResponse }) {
  const v = VERDICT[data.verdict];
  const r = data.recommendation;
  const warranty = data.assumptions.warranty_years;
  return (
    <section aria-labelledby="verdict-heading" className={`rounded-2xl border-2 p-6 ${v.tone}`}>
      <p className="mb-1 text-sm font-medium uppercase tracking-wide text-slate-300">Our answer</p>
      <h2 id="verdict-heading" className="mb-2 flex items-center gap-3 text-3xl font-bold text-white sm:text-4xl">
        <span aria-hidden="true" className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-current text-2xl">{v.icon}</span>
        {v.title}
      </h2>
      <p className="mb-3 text-lg text-slate-100">{v.summary(warranty)}</p>
      <p className="text-slate-200">
        {r.chosen_by === "best_value" ? "The best-value option for your home is a " : "For the battery you chose: a "}
        <strong className="text-white">{r.battery_label} battery</strong> on{" "}
        <strong className="text-white">{r.tariff_name}</strong>, at about <strong className="text-white">{gbp(r.installed_price)}</strong> fitted.
      </p>
    </section>
  );
}

// ── 2. Headline numbers ───────────────────────────────────────────────────────

function Stat({ label, value, note }: { label: React.ReactNode; value: string; note?: string }) {
  return (
    <div className="rounded-xl border border-slate-700 bg-[#0f1f38] p-4">
      <dt className="text-sm text-slate-300">{label}</dt>
      <dd className="mt-1 text-2xl font-bold text-white">{value}</dd>
      {note && <dd className="mt-1 text-sm text-slate-300">{note}</dd>}
    </div>
  );
}

export function HeadlineNumbers({ data }: { data: AssessResponse }) {
  const h = data.headline;
  const life = data.assumptions.battery_life_years;
  return (
    <section aria-labelledby="numbers-heading">
      <h2 id="numbers-heading" className="sr-only">The numbers</h2>
      <dl className="grid gap-3 sm:grid-cols-2">
        <Stat label="Cost to buy and fit" value={gbp(h.installed_cost.likely)}
          note={`Typically ${gbpRange(h.installed_cost.low, h.installed_cost.high)}`} />
        <Stat label="Saving in the first year" value={`${gbp(h.year1_battery_saving)} a year`}
          note={`About ${gbpRange(h.average_yearly_saving.low, h.average_yearly_saving.high)} a year on average over ${life} years`} />
        <Stat label={<><Term k="payback">Pays back</Term> in</>} value={years(h.payback_years.likely, life)}
          note={paybackNote(h.payback_years.low, h.payback_years.high, life)} />
        <Stat label={`Money ahead after ${life} years`} value={gbp(h.lifetime_net_gain.likely)}
          note={`Could be ${gbpRange(h.lifetime_net_gain.low, h.lifetime_net_gain.high)}`} />
      </dl>
      <p className="mt-3 text-sm text-slate-300">
        Savings are what the battery adds on top of the best tariff you could switch to without one.
      </p>
    </section>
  );
}

// ── 3. Confidence ─────────────────────────────────────────────────────────────

export function ConfidenceBadge({ data, query }: { data: AssessResponse; query: string }) {
  const c = CONFIDENCE[data.usage.confidence] ?? CONFIDENCE.estimate;
  const upgrade = data.usage.confidence === "estimate" || data.usage.confidence === "low";
  return (
    <section aria-labelledby="confidence-heading" className="rounded-xl border border-slate-700 p-4">
      <h2 id="confidence-heading" className="mb-1 font-semibold text-white">
        How sure is this? <span className="ml-1 rounded-full border border-slate-500 px-2 py-0.5 text-sm font-normal text-slate-200">{c.label}</span>
      </h2>
      <p className="text-sm text-slate-300">
        {c.text} Your home uses about {kwh(data.usage.annual_kwh)} a year in our model.
      </p>
      {upgrade && (
        <p className="mt-2 text-sm">
          <Link href={stepHref(ROUTE_PATHS.upload, withRoute("upload", query))} className="text-white underline underline-offset-4">
            Add your smart meter data for a firmer answer
          </Link>
        </p>
      )}
    </section>
  );
}

// ── 5. Where the saving comes from ────────────────────────────────────────────

export function SavingBreakdown({ data }: { data: AssessResponse }) {
  const b = data.saving_breakdown;
  const parts = (["time_shifting", "solar_storage", "other"] as const)
    .map((k) => ({ key: k, label: BREAKDOWN_LABELS[k], value: b[k] }))
    .filter((p) => Math.abs(p.value) >= 1);
  const max = Math.max(1, ...parts.map((p) => Math.abs(p.value)));
  // Worked out from the rounded figures shown, so the sentence adds up as written.
  const switchPart = Math.round(b.total) - Math.round(data.headline.year1_battery_saving);
  return (
    <section aria-labelledby="breakdown-heading">
      <h2 id="breakdown-heading" className="mb-1 text-xl font-semibold">Where the saving comes from</h2>
      <p className="mb-4 text-sm text-slate-300">
        In the first year, the battery saves {gbp(b.total)} compared with being on {data.recommendation.tariff_name} without one.
        {switchPart >= 1 && (
          <>
            {" "}Of that, {gbp(switchPart)} you could also get just by switching to the best
            tariff without a battery, so we count {gbp(data.headline.year1_battery_saving)} as the battery&apos;s own saving.
          </>
        )}
      </p>
      {parts.length === 0 ? (
        <p className="text-slate-300">On this tariff a battery doesn&apos;t save anything: there&apos;s no cheaper time to charge it.</p>
      ) : (
        <ul className="space-y-3">
          {parts.map((p) => (
            <li key={p.key}>
              <div className="mb-1 flex items-baseline justify-between gap-3">
                <span className="text-slate-100">{p.label}</span>
                <span className="font-semibold text-white">{gbp(p.value)}</span>
              </div>
              <div className="h-3 rounded-full bg-slate-800" aria-hidden="true">
                <div className={`h-3 rounded-full ${p.value >= 0 ? "bg-[#f97316]" : "bg-slate-400"}`}
                  style={{ width: `${Math.max(2, (Math.abs(p.value) / max) * 100)}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
