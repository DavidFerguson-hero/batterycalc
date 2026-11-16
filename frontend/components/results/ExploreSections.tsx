"use client";


import Link from "next/link";

import Term from "@/components/Term";
import ShareBar from "@/components/results/Share";
import type { AssessResponse } from "@/lib/api";
import { VERDICT, gbp, gbpRange, plainUpgradeLabel, ukDate, years } from "@/lib/format";
import { solarAssumption, solarContextNote } from "@/lib/solar";

const card = "rounded-xl border border-slate-700 bg-[#0f1f38]";
const sub = "text-sm text-slate-300";

function VerdictWords({ v }: { v: AssessResponse["verdict"] }) {
  return (
    <span className="whitespace-nowrap">
      <span aria-hidden="true">{VERDICT[v].icon} </span>{VERDICT[v].title}
    </span>
  );
}

// ── 6. Size comparison ────────────────────────────────────────────────────────

export function SizeComparison({ data }: { data: AssessResponse }) {
  const s = data.size_comparison;
  const life = data.assumptions.battery_life_years;
  const best = s.best_value;
  const chosen = data.recommendation.battery_kwh;
  // Only worth a sentence when the bigger battery really does save more (sizes often tie).
  const biggest = s.all_sizes.find((r) => r.kwh === s.biggest_saving_kwh);
  const biggestDiffers = !!biggest && biggest.kwh !== best.kwh && biggest.year1_battery_saving - best.year1_battery_saving >= 10;
  return (
    <section aria-labelledby="sizes-heading">
      <h2 id="sizes-heading" className="mb-1 text-xl font-semibold">Which size is best value</h2>
      <p className={`mb-4 ${sub}`}>
        A <strong className="text-white">{best.label}</strong> battery leaves you the most money ahead after {life} years.
        {biggestDiffers && (
          <> A {s.biggest_saving_kwh} kWh battery saves a little more each year, but the extra saving doesn&apos;t cover its higher price.</>
        )}
        {s.smaller && (
          <> A smaller {s.smaller.label} battery costs {gbp(best.installed_cost - s.smaller.installed_cost)} less
            and pays back in {years(s.smaller.payback_years, life)}.</>
        )}
      </p>
      <div className={`${card} overflow-x-auto`} role="region" aria-labelledby="sizes-heading" tabIndex={0}>
        <table className="w-full min-w-[36rem] text-right text-sm">
          <caption className="sr-only">Each battery size on its best tariff</caption>
          <thead className="text-slate-200">
            <tr>
              <th scope="col" className="px-3 py-2 text-left">Size</th>
              <th scope="col" className="px-3 py-2">Cost fitted</th>
              <th scope="col" className="px-3 py-2">First-year saving</th>
              <th scope="col" className="px-3 py-2">Pays back in</th>
              <th scope="col" className="px-3 py-2">Ahead after {life} years</th>
              <th scope="col" className="px-3 py-2 text-left">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {s.all_sizes.map((r) => {
              const isBest = r.kwh === best.kwh;
              return (
                <tr key={r.kwh} className={`border-t border-slate-800 ${isBest ? "bg-[#f97316]/10 text-white" : "text-slate-200"}`}>
                  <th scope="row" className="px-3 py-2 text-left font-semibold">
                    {r.label}
                    {isBest && <span className="ml-2 rounded-full bg-[#f97316] px-2 py-0.5 text-xs font-semibold text-[#0a1628]">Best value</span>}
                    {r.kwh === chosen && !isBest && <span className="ml-2 text-xs font-normal text-slate-300">(yours)</span>}
                  </th>
                  <td className="px-3 py-2">{gbp(r.installed_cost)}</td>
                  <td className="px-3 py-2">{gbp(r.year1_battery_saving)}</td>
                  <td className="px-3 py-2">{years(r.payback_years, life)}</td>
                  <td className="px-3 py-2">{gbp(r.lifetime_net_gain)}</td>
                  <td className="px-3 py-2 text-left"><VerdictWords v={r.verdict} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className={`mt-2 ${sub}`}>Each size is shown on the tariff that suits it best, at a typical fitted price.</p>
    </section>
  );
}

// ── 7. Tariff check ───────────────────────────────────────────────────────────

export function TariffCheck({ data }: { data: AssessResponse }) {
  const tc = data.tariff_check;
  const cur = tc.current as { name: string; annual_cost_no_battery: number; annual_cost_with_battery: number };
  const curName = cur.name === "Your current tariff" ? "your current tariff" : cur.name;
  // The API returns these as a name → £ map.
  const sv = {
    switchOnly: tc.savings.switch_tariff_only ?? 0,
    batteryOnCurrent: tc.savings.battery_on_current_tariff ?? 0,
    best: tc.savings.best_tariff_and_battery ?? 0,
  };
  const flatNoGain = sv.batteryOnCurrent < 1;
  const rows = [
    { label: `Now, on ${curName}`, value: cur.annual_cost_no_battery, note: null as string | null },
    { label: `Switch to ${tc.best_no_battery.name}, no battery`, value: tc.best_no_battery.annual_cost,
      note: sv.switchOnly >= 1 ? `saves ${gbp(sv.switchOnly)} a year` : "no cheaper than now" },
    { label: `Battery on ${tc.best_with_battery.name}`, value: tc.best_with_battery.annual_cost,
      note: `saves ${gbp(sv.best)} a year` },
  ];
  return (
    <section aria-labelledby="tariff-heading">
      <h2 id="tariff-heading" className="mb-1 text-xl font-semibold">Your <Term k="tariff" /></h2>
      <p className={`mb-4 ${sub}`}>Yearly electricity bill, including the <Term k="standing_charge">standing charge</Term>.</p>
      <ol className="grid gap-3 sm:grid-cols-3">
        {rows.map((r) => (
          <li key={r.label} className={`${card} p-4`}>
            <p className="text-sm text-slate-300">{r.label}</p>
            <p className="mt-1 text-2xl font-bold text-white">{gbp(r.value)}<span className="text-base font-normal text-slate-300"> a year</span></p>
            {r.note && <p className="mt-1 text-sm text-slate-300">{r.note}</p>}
          </li>
        ))}
      </ol>
      {tc.switch_first && (
        <p className="mt-4 rounded-xl border-2 border-[#fbbf24] bg-[#fbbf24]/10 p-4 text-slate-100">
          <strong className="text-white">Switch tariff first.</strong> Most of what you could save
          ({gbp(sv.switchOnly)} of {gbp(sv.best)} a year) comes from
          switching to {tc.best_no_battery.name}, which costs nothing. You can decide on a battery afterwards.
        </p>
      )}
      {flatNoGain && (
        <p className={`mt-4 ${sub}`}>
          On a single-rate tariff a battery can&apos;t save anything: there&apos;s no cheaper time to charge it.
          It only pays when paired with a <Term k="time_of_use">time-of-use</Term> tariff.
        </p>
      )}
      <details className="mt-3">
        <summary className="cursor-pointer text-sm text-slate-200 underline underline-offset-4">
          Compare all {tc.by_tariff.length} tariffs
        </summary>
        <div className={`mt-2 max-h-80 overflow-auto ${card}`} tabIndex={0} role="region" aria-label="All tariffs">
          <table className="w-full text-right text-sm">
            <caption className="sr-only">Yearly bill on each tariff, with and without the battery</caption>
            <thead className="sticky top-0 bg-[#13233d] text-slate-200">
              <tr>
                <th scope="col" className="px-3 py-2 text-left">Tariff</th>
                <th scope="col" className="px-3 py-2">Without a battery</th>
                <th scope="col" className="px-3 py-2">With the battery</th>
              </tr>
            </thead>
            <tbody>
              {tc.by_tariff.map((r) => (
                <tr key={r.key} className="border-t border-slate-800 text-slate-200">
                  <th scope="row" className="px-3 py-1.5 text-left font-normal">{r.name}</th>
                  <td className="px-3 py-1.5">{gbp(r.annual_cost_no_battery)}</td>
                  <td className="px-3 py-1.5">{gbp(r.annual_cost_with_battery)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}

// ── 10. Context: other upgrades ───────────────────────────────────────────────

export function ContextPanel({ data }: { data: AssessResponse }) {
  const solarNote = solarContextNote(data.usage.solar);
  const items = Object.entries(data.context_costs).filter((e): e is [string, NonNullable<(typeof e)[1]>] => !!e[1]);
  return (
    <section aria-labelledby="context-heading" className="text-sm">
      <h2 id="context-heading" className="mb-1 text-lg font-semibold">Other upgrades, for context</h2>
      <p className={`mb-3 ${sub}`}>
        Typical fitted prices, in case you&apos;re weighing a battery against other changes.
        {solarNote && ` ${solarNote}`}
      </p>
      <ul className="grid gap-3 sm:grid-cols-3">
        {items.map(([key, c]) => (
          <li key={key} className="rounded-lg border border-slate-700 p-3">
            <p className="font-medium text-slate-100">{plainUpgradeLabel(c.label)}</p>
            <p className="text-slate-300">About {gbp(c.typical)} ({gbpRange(c.low, c.high)})</p>
            {c.grant && c.after_grant?.typical !== undefined && (
              <p className="mt-1 text-slate-300">
                About {gbp(c.after_grant.typical)} after the {gbp(c.grant)} {c.grant_name ?? "grant"}.
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

// ── 11. Next steps ────────────────────────────────────────────────────────────

export const INSTALLER_QUESTIONS = [
  "Is the price fully fitted: battery, inverter, wiring, any scaffolding, and VAT?",
  "How much of the battery's capacity can I actually use, in kWh?",
  "How long is the warranty, and how much capacity is guaranteed at the end of it?",
  "Are you certified by MCS (the Microgeneration Certification Scheme) and a member of a consumer code such as RECC (Renewable Energy Consumer Code)?",
  "Will you set it up to charge on my time-of-use tariff, and show me how to change the times?",
  "Will you tell my local electricity network operator about the battery, as required?",
  "Will it keep the lights on in a power cut, and does that cost extra?",
  "Can I add solar panels later without replacing the inverter?",
];

export function NextSteps({ data }: { data: AssessResponse }) {
  const fp = data.fair_price;
  const priceNote =
    data.recommendation.chosen_by === "you" && fp.your_price_is && fp.your_price_is !== "within_range" && fp.your_price
      ? ` The ${gbp(fp.your_price)} you entered is ${fp.your_price_is === "above_range" ? "above" : "below"} that range${
          fp.your_price_is === "above_range" ? ", so it's worth getting another quote" : ""}.`
      : "";
  return (
    <section aria-labelledby="next-heading">
      <h2 id="next-heading" className="mb-4 text-xl font-semibold">Next steps</h2>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className={`${card} p-5`}>
          <h3 className="mb-2 font-semibold text-white">A fair price</h3>
          <p className="text-slate-200">
            A {fp.kwh} kWh battery usually costs <strong className="text-white">{gbpRange(fp.low, fp.high)}</strong> fitted,
            typically about {gbp(fp.typical)}.{priceNote}
          </p>
          <p className={`mt-2 ${sub}`}>Prices as of {ukDate(fp.as_of)}. Get at least three quotes.</p>
        </div>
        <div className={`${card} p-5`}>
          <h3 className="mb-2 font-semibold text-white">Share or save your answer</h3>
          <ShareBar route={data.usage.route} />
        </div>
      </div>
      <div className={`mt-4 ${card} p-5`}>
        <h3 className="mb-2 font-semibold text-white">Questions to ask an installer</h3>
        <ul className="list-disc space-y-1.5 pl-5 text-slate-200">
          {INSTALLER_QUESTIONS.map((q) => <li key={q}>{q}</li>)}
        </ul>
      </div>
    </section>
  );
}

// ── 12. Assumptions ───────────────────────────────────────────────────────────

export function Assumptions({ data }: { data: AssessResponse }) {
  const solar = solarAssumption(data.usage.solar);
  const a = data.assumptions;
  const g = a.price_growth_pct;
  const pct = (n: number) => `${Math.round(n * 100)}%`;
  const worthShare = a.verdict_thresholds.worth_it_share_of_warranty ?? 0.7;
  const rows: [React.ReactNode, React.ReactNode][] = [
    ["Battery life", `${a.battery_life_years} years`],
    [<Term key="w" k="warranty">Warranty</Term>, `${a.warranty_years} years`],
    ["Capacity lost each year", `${a.capacity_loss_pct_per_year}%`],
    ["Electricity prices rise each year", `${g.central}% likely (${g.low}% pessimistic, ${g.high}% optimistic)`],
    [<Term key="i" k="inverter">Inverter</Term>, a.inverter_replacement_year
      ? `Replaced in year ${a.inverter_replacement_year}, about ${gbp(a.inverter_replacement_cost)}`
      : "Not replaced"],
    ["“Worth it” means", `Pays back within ${years(worthShare * a.warranty_years)} (${pct(worthShare)} of the warranty)`],
    ["“Borderline” means", `Pays back later than that, but within the ${a.warranty_years}-year warranty`],
    // A single unit rate only means something on a flat-rate tariff.
    ...((data.tariff_check.current as { key?: string }).key === "current"
      ? [["Your electricity rate", `${data.usage.unit_rate_p}p per kWh`] as [string, string]]
      : []),
    [data.usage.solar?.modelled ? "Electricity use modelled (before solar)" : "Electricity use modelled",
      `${Math.round(data.usage.annual_kwh).toLocaleString("en-GB")} kWh a year`],
    ...(solar ? [["Solar panels", solar] as [string, string]] : []),
    ["Battery and fitting prices", `As of ${ukDate(a.costs_as_of)}`],
    ["Tariffs", `Checked ${ukDate(a.tariffs_checked)}`],
  ];
  return (
    <section aria-labelledby="assumptions-heading">
      <details className={`${card} p-5`}>
        <summary className="cursor-pointer">
          <h2 id="assumptions-heading" className="inline text-lg font-semibold">Our assumptions</h2>
        </summary>
        <dl className="mt-4 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
          {rows.map(([k, v], i) => (
            <div key={i} className="contents">
              <dt className="text-slate-300">{k}</dt>
              <dd className="text-slate-100">{v}</dd>
            </div>
          ))}
        </dl>
        <p className={`mt-4 ${sub}`}>
          Savings are compared with the best tariff you could switch to without a battery.
          Figures are estimates, not financial advice.{" "}
          <Link href="/how-we-calculate" className="text-white underline underline-offset-4">How we calculate</Link>
        </p>
      </details>
    </section>
  );
}
