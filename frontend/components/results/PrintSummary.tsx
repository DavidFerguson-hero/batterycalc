"use client";

import { createPortal } from "react-dom";

import type { AssessResponse } from "@/lib/api";
import { BREAKDOWN_LABELS, CONFIDENCE, VERDICT, gbp, gbpRange, kwh, paybackNote, ukDate, years } from "@/lib/format";
import { milestones, printableUrl } from "@/lib/summary";

import { INSTALLER_QUESTIONS } from "./ExploreSections";

/**
 * The one-page summary that prints (or saves as PDF) instead of the interactive page.
 * It sits directly under <body> so the print stylesheet can hide everything else
 * (see .print-root in globals.css). Hidden on screen.
 * Uses its own heading levels, as it is never shown alongside the page.
 */
function H({ children }: { children: React.ReactNode }) {
  return <h2 className="mb-[1mm] mt-[3mm] border-b border-black/30 pb-[0.5mm] text-[10.5pt] font-bold">{children}</h2>;
}

export default function PrintSummary({ data }: { data: AssessResponse }) {
  // Only ever rendered in the browser, once the answer has arrived.
  if (typeof document === "undefined") return null;
  const href = window.location.href;
  const today = ukDate(new Date().toISOString().slice(0, 10));

  const v = VERDICT[data.verdict];
  const r = data.recommendation;
  const h = data.headline;
  const a = data.assumptions;
  const life = a.battery_life_years;
  const tc = data.tariff_check;
  const cur = tc.current as { name: string; annual_cost_no_battery: number };
  const be = data.break_even;
  const marks = milestones(be.years, be.likely, [0, 5, 10, life]);
  const low = milestones(be.years, be.pessimistic, [0, 5, 10, life]);
  const high = milestones(be.years, be.optimistic, [0, 5, 10, life]);
  const parts = (["time_shifting", "solar_storage", "other"] as const)
    .map((k) => ({ label: BREAKDOWN_LABELS[k], value: data.saving_breakdown[k] }))
    .filter((p) => Math.abs(p.value) >= 1);
  const conf = CONFIDENCE[data.usage.confidence] ?? CONFIDENCE.estimate;
  const growth = a.price_growth_pct;

  return createPortal(
    <div className="print-root bg-white font-sans text-[9pt] leading-snug text-black">
      <header className="flex items-baseline justify-between border-b-2 border-black pb-[1.5mm]">
        <p className="text-[15pt] font-bold">Is a battery worth it for your home?</p>
        <p className="text-[8.5pt]">BatterySizer · {today}</p>
      </header>

      <section className="mt-[3mm] rounded border-2 border-black p-[3mm]">
        <p className="text-[14pt] font-bold">{v.icon} {v.title}</p>
        <p>{v.summary(a.warranty_years)}</p>
        <p className="mt-[1mm]">
          {r.chosen_by === "best_value" ? "Best value for your home: " : "The battery you chose: "}
          <strong>{r.battery_label} battery</strong> on <strong>{r.tariff_name}</strong>, about <strong>{gbp(r.installed_price)}</strong> fitted.
        </p>
      </section>

      <dl className="mt-[3mm] grid grid-cols-4 gap-[2mm]">
        {[
          ["Cost to buy and fit", gbp(h.installed_cost.likely), `Could be ${gbpRange(h.installed_cost.low, h.installed_cost.high)}`],
          ["Saving in the first year", gbp(h.year1_battery_saving), `Could be ${gbpRange(h.average_yearly_saving.low, h.average_yearly_saving.high)} a year on average`],
          ["Pays back in", years(h.payback_years.likely, life), paybackNote(h.payback_years.low, h.payback_years.high, life)],
          [`Money ahead after ${life} years`, gbp(h.lifetime_net_gain.likely), `Could be ${gbpRange(h.lifetime_net_gain.low, h.lifetime_net_gain.high)}`],
        ].map(([k, val, note]) => (
          <div key={k} className="rounded border border-black/40 p-[2mm]">
            <dt className="text-[8pt]">{k}</dt>
            <dd className="text-[13pt] font-bold">{val}</dd>
            <dd className="text-[8pt]">{note}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-[1mm] text-[8pt]">
        Savings are on top of the best tariff you could switch to without a battery. How sure: {conf.label.toLowerCase()}. {conf.text}{" "}
        Your home uses about {kwh(data.usage.annual_kwh)} a year in our model.
      </p>

      <div className="grid grid-cols-2 gap-x-[6mm]">
        <div>
          <H>Money over {life} years</H>
          <table className="w-full text-right">
            <thead>
              <tr className="text-[8pt]">
                <th scope="col" className="text-left font-normal">After</th>
                <th scope="col" className="font-normal">Pessimistic</th>
                <th scope="col" className="font-semibold">Likely</th>
                <th scope="col" className="font-normal">Optimistic</th>
              </tr>
            </thead>
            <tbody>
              {marks.map((m, i) => (
                <tr key={m.year} className="border-t border-black/15">
                  <th scope="row" className="text-left font-normal">{m.year === 0 ? "Fitting day" : `${m.year} years`}</th>
                  <td>{gbp(low[i]?.value ?? 0)}</td>
                  <td className="font-semibold">{gbp(m.value)}</td>
                  <td>{gbp(high[i]?.value ?? 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <H>Where the saving comes from</H>
          {parts.length ? (
            <ul>
              {parts.map((p) => <li key={p.label}>{p.label}: <strong>{gbp(p.value)}</strong> a year</li>)}
            </ul>
          ) : <p>On this tariff a battery doesn&apos;t save anything.</p>}

          <H>Your tariff (yearly bill)</H>
          <ul>
            <li>Now, on {cur.name === "Your current tariff" ? "your current tariff" : cur.name}: <strong>{gbp(cur.annual_cost_no_battery)}</strong></li>
            <li>{tc.best_no_battery.name}, no battery: <strong>{gbp(tc.best_no_battery.annual_cost)}</strong></li>
            <li>Battery on {tc.best_with_battery.name}: <strong>{gbp(tc.best_with_battery.annual_cost)}</strong></li>
          </ul>
          {tc.switch_first && <p className="mt-[1mm] font-semibold">Switch tariff first: it gives most of the saving and costs nothing.</p>}
        </div>

        <div>
          <H>Battery sizes (each on its best tariff)</H>
          <table className="w-full text-right">
            <thead>
              <tr className="text-[8pt]">
                <th scope="col" className="text-left font-normal">Size</th>
                <th scope="col" className="font-normal">Fitted</th>
                <th scope="col" className="font-normal">Year 1 saving</th>
                <th scope="col" className="font-normal">Pays back</th>
                <th scope="col" className="font-normal">Ahead</th>
              </tr>
            </thead>
            <tbody>
              {data.size_comparison.all_sizes.map((s) => (
                <tr key={s.kwh} className={`border-t border-black/15 ${s.kwh === data.size_comparison.best_value.kwh ? "font-bold" : ""}`}>
                  <th scope="row" className={`text-left ${s.kwh === data.size_comparison.best_value.kwh ? "font-bold" : "font-normal"}`}>{s.label}{s.kwh === data.size_comparison.best_value.kwh ? " ★" : ""}</th>
                  <td>{gbp(s.installed_cost)}</td>
                  <td>{gbp(s.year1_battery_saving)}</td>
                  <td>{s.payback_years === null ? "—" : `${Math.round(s.payback_years * 10) / 10} yrs`}</td>
                  <td>{gbp(s.lifetime_net_gain)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[8pt]">★ best value. “—” means it doesn&apos;t pay back within {life} years.</p>

          <H>A fair price</H>
          <p>
            A {data.fair_price.kwh} kWh battery usually costs <strong>{gbpRange(data.fair_price.low, data.fair_price.high)}</strong> fitted,
            typically about {gbp(data.fair_price.typical)}. Get at least three quotes.
          </p>
        </div>
      </div>

      <H>Questions to ask an installer</H>
      <ol className="list-decimal columns-2 gap-x-[6mm] pl-[4mm] text-[8.5pt]">
        {INSTALLER_QUESTIONS.map((q) => <li key={q} className="break-inside-avoid">{q}</li>)}
      </ol>

      <footer className="mt-[3mm] border-t border-black/30 pt-[1.5mm] text-[7.5pt]">
        <p>
          Assumes a {life}-year battery life, a {a.warranty_years}-year warranty, {a.capacity_loss_pct_per_year}% capacity lost each year,
          electricity prices rising {growth.central}% a year ({growth.low}% to {growth.high}%)
          {a.inverter_replacement_year ? ` and the inverter replaced in year ${a.inverter_replacement_year} (about ${gbp(a.inverter_replacement_cost)})` : ""}.
          Prices as of {ukDate(a.costs_as_of)}; tariffs checked {ukDate(a.tariffs_checked)}. Figures are estimates, not financial advice.
        </p>
        {href && <p className="mt-[1mm] break-all">See the full answer: {printableUrl(href)}</p>}
      </footer>
    </div>,
    document.body,
  );
}
