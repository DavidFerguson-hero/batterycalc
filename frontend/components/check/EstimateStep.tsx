"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useId, useState } from "react";

import Term from "@/components/Term";
import { ApiError, type EpcHome, lookupEpc } from "@/lib/api";
import {
  type EstimateAnswers, type Heating, PROPERTY_LABELS, PROPERTY_TYPES, type PropertyType,
  isComplete, parseEstimate, suggestKwh, writeEstimate,
} from "@/lib/estimate";
import { parseJourney, stepHref, writeJourney } from "@/lib/journey";

const field = "w-full rounded-lg border border-slate-500 bg-[#0a1628] px-3 py-3 text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#f97316]";
const primary = "rounded-full bg-[#f97316] px-6 py-3 font-semibold text-[#0a1628] transition-colors hover:bg-[#fb8a3c] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-200";

type Lookup =
  | { state: "idle" }
  | { state: "searching" }
  | { state: "found"; homes: EpcHome[] }
  | { state: "none" }
  | { state: "unavailable"; message: string };

function Choice<T extends string | number>({
  name, legend, hint, value, options, onChange,
}: {
  name: string; legend: string; hint?: React.ReactNode; value: T | null;
  options: { value: T; label: string }[]; onChange: (v: T) => void;
}) {
  return (
    <fieldset className="mb-6">
      <legend className="mb-1 font-semibold text-white">{legend}</legend>
      {hint && <p className="mb-2 text-sm text-slate-300">{hint}</p>}
      <div className="flex flex-wrap gap-2">
        {options.map((o) => {
          const id = `${name}-${o.value}`;
          const checked = value === o.value;
          return (
            <div key={id}>
              <input type="radio" id={id} name={name} checked={checked} onChange={() => onChange(o.value)} className="peer sr-only" />
              <label
                htmlFor={id}
                className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border px-4 py-2 peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[#f97316] ${
                  checked ? "border-[#f97316] bg-[#f97316]/10 font-semibold text-white" : "border-slate-600 text-slate-100 hover:border-slate-400"
                }`}
              >
                <span aria-hidden="true" className={`flex h-4 w-4 items-center justify-center rounded-full border-2 ${checked ? "border-[#f97316]" : "border-slate-400"}`}>
                  {checked && <span className="h-2 w-2 rounded-full bg-[#f97316]" />}
                </span>
                {o.label}
              </label>
            </div>
          );
        })}
      </div>
    </fieldset>
  );
}

export default function EstimateStep() {
  const router = useRouter();
  const pathname = usePathname();
  const query = useSearchParams().toString();
  const journey = parseJourney(query);
  const answers = parseEstimate(query);
  const hasEv = journey.home.ev !== "none";

  const [postcode, setPostcode] = useState("");
  const [lookup, setLookup] = useState<Lookup>({ state: "idle" });
  const [picked, setPicked] = useState<string | null>(null);        // certificate number, or "manual"
  const [epcKwh, setEpcKwh] = useState<number | null>(null);         // the EPC-based estimate, incl. electric heating
  const [notes, setNotes] = useState<string[]>([]);
  // Step-1 answers a picked home's certificate filled in, so picking a different home can undo them.
  const [addedByEpc, setAddedByEpc] = useState<("heat_pump" | "solar" | "battery")[]>([]);
  const [kwhTyped, setKwhTyped] = useState(false);                    // homeowner entered their own figure
  const ids = { postcode: useId(), kwh: useId(), miles: useId(), beds: useId(), people: useId() };

  // The details form shows once there's something to show: a picked home, manual entry, or answers in the URL.
  const showDetails = picked !== null || answers.propertyType !== null;

  function save(next: EstimateAnswers, extra?: (q: string) => string) {
    let q = writeEstimate(next, query);
    if (extra) q = extra(q);
    router.replace(stepHref(pathname, q), { scroll: false });
  }

  /** Update one answer, refreshing the suggested annual use unless the homeowner typed their own. */
  function update(patch: Partial<EstimateAnswers>) {
    const next = { ...answers, ...patch };
    if (!kwhTyped && next.propertyType && next.bedrooms) {
      next.annualKwh = suggestKwh(next.propertyType, next.bedrooms, next.people, next.heating === "electric" ? epcKwh : null);
    }
    save(next);
  }

  async function find(e: React.FormEvent) {
    e.preventDefault();
    if (!postcode.trim()) return;
    setLookup({ state: "searching" });
    try {
      const homes = await lookupEpc(postcode);
      setLookup(homes.length ? { state: "found", homes } : { state: "none" });
    } catch (err) {
      const message = err instanceof ApiError && err.status === 422
        ? "That doesn't look like a postcode. Please check it and try again."
        : "We can't look up homes on the EPC register right now.";
      setLookup({ state: "unavailable", message });
    }
  }

  function pick(home: EpcHome) {
    setPicked(home.certificate_number);
    setKwhTyped(false);
    const heatingKwh = home.heating_type === "electric" ? home.annual_kwh : null;
    setEpcKwh(heatingKwh);
    const beds = Math.min(Math.max(home.bedrooms, 1), 5);
    const next: EstimateAnswers = {
      ...answers,
      propertyType: home.property_type,
      bedrooms: beds,
      heating: home.heating_type,
      floorArea: home.floor_area_m2 ? Math.round(home.floor_area_m2) : null,
      epcRating: home.epc_rating,
      annualKwh: suggestKwh(home.property_type, beds, answers.people, heatingKwh),
    };
    // Things on the certificate the homeowner didn't mention in step 1. First undo anything a
    // previously picked home added, so choosing the wrong home and then the right one is clean.
    const home2 = { ...journey.home };
    for (const item of addedByEpc) home2[item] = "none";
    const added: string[] = [];
    const now: ("heat_pump" | "solar" | "battery")[] = [];
    if (home.has_heat_pump && home2.heat_pump === "none") { home2.heat_pump = "have"; added.push("a heat pump"); now.push("heat_pump"); }
    if (home.has_solar && home2.solar === "none") { home2.solar = "have"; added.push("solar panels"); now.push("solar"); }
    if (home.has_battery && home2.battery === "none") { home2.battery = "have"; added.push("a home battery"); now.push("battery"); }
    setAddedByEpc(now);
    setNotes(added.length ? [`Your EPC says the home has ${added.join(" and ")}, so we've added that to your answers.`] : []);
    save(next, (q) => writeJourney({ ...journey, home: home2 }, q));
  }

  function manual() {
    setPicked("manual");
    setEpcKwh(null);
    setNotes([]);
    if (addedByEpc.length) {
      const home2 = { ...journey.home };
      for (const item of addedByEpc) home2[item] = "none";
      setAddedByEpc([]);
      router.replace(stepHref(pathname, writeJourney({ ...journey, home: home2 }, query)), { scroll: false });
    }
  }

  const complete = isComplete(answers);

  return (
    <>
      {/* ── Find your home ─────────────────────────────────────────── */}
      <section aria-labelledby="find-heading" className="rounded-xl border border-slate-700 bg-[#0f1f38] p-5">
        <h2 id="find-heading" className="mb-1 text-xl font-semibold">Find your home</h2>
        <p className="mb-4 text-sm text-slate-300">
          We&apos;ll look it up on the public <Term k="epc" /> register to fill in the details. Your postcode isn&apos;t stored.
        </p>
        <form onSubmit={find} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="sm:w-56">
            <label htmlFor={ids.postcode} className="mb-1 block text-slate-200">Postcode</label>
            <input
              id={ids.postcode}
              value={postcode}
              onChange={(e) => setPostcode(e.target.value)}
              autoComplete="postal-code"
              inputMode="text"
              placeholder="e.g. SW1A 1AA"
              className={`${field} uppercase`}
            />
          </div>
          <button type="submit" className={primary} disabled={lookup.state === "searching"}>
            {lookup.state === "searching" ? "Looking…" : "Find my home"}
          </button>
        </form>

        <div aria-live="polite" className="mt-4">
          {lookup.state === "none" && (
            <p className="text-slate-200">We couldn&apos;t find any homes with an EPC at that postcode. Please check it, or enter your details below.</p>
          )}
          {lookup.state === "unavailable" && (
            <p className="text-slate-200">{lookup.message} Please enter your home&apos;s details below instead.</p>
          )}
          {lookup.state === "found" && (
            <fieldset>
              <legend className="mb-2 font-semibold text-white">Which is your home?</legend>
              <ul className="max-h-80 space-y-2 overflow-y-auto pr-1">
                {lookup.homes.map((h) => {
                  const id = `home-${h.certificate_number}`;
                  const checked = picked === h.certificate_number;
                  return (
                    <li key={h.certificate_number}>
                      <input type="radio" id={id} name="home" checked={checked} onChange={() => pick(h)} className="peer sr-only" />
                      <label
                        htmlFor={id}
                        className={`block cursor-pointer rounded-lg border px-4 py-3 peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[#f97316] ${
                          checked ? "border-[#f97316] bg-[#f97316]/10" : "border-slate-600 hover:border-slate-400"
                        }`}
                      >
                        <span className={`block ${checked ? "font-semibold text-white" : "text-slate-100"}`}>
                          {checked && <span aria-hidden="true">✓ </span>}{h.address}
                        </span>
                        <span className="block text-sm text-slate-300">
                          {h.dwelling_type ?? PROPERTY_LABELS[h.property_type]}
                          {h.epc_rating ? ` · EPC ${h.epc_rating}` : ""}
                          {h.floor_area_m2 ? ` · ${Math.round(h.floor_area_m2)} m²` : ""}
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            </fieldset>
          )}
          {notes.map((n) => <p key={n} className="mt-3 text-sm text-[#fdba74]">{n}</p>)}
        </div>

        {!showDetails && (
          <button type="button" onClick={manual} className="mt-4 text-sm text-slate-300 underline underline-offset-4 hover:text-white">
            {lookup.state === "found" ? "My home isn't listed" : "Enter my home's details myself"}
          </button>
        )}
        {lookup.state === "found" && showDetails && picked !== "manual" && (
          <button type="button" onClick={manual} className="mt-4 text-sm text-slate-300 underline underline-offset-4 hover:text-white">
            My home isn&apos;t listed
          </button>
        )}
      </section>

      {/* ── About your home ────────────────────────────────────────── */}
      {(showDetails || lookup.state === "unavailable" || lookup.state === "none") && (
        <section aria-labelledby="details-heading" className="mt-8">
          <h2 id="details-heading" className="mb-1 text-xl font-semibold">About your home</h2>
          <p className="mb-6 text-sm text-slate-300">
            {picked && picked !== "manual" ? "Filled in from your EPC. Change anything that's not right." : "A few details so we can estimate your use."}
          </p>

          <Choice<PropertyType>
            name="prop" legend="Type of home" value={answers.propertyType}
            options={PROPERTY_TYPES.map((p) => ({ value: p, label: PROPERTY_LABELS[p] }))}
            onChange={(v) => update({ propertyType: v, bedrooms: answers.bedrooms ?? 3 })}
          />

          <div className="mb-6 grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor={ids.beds} className="mb-1 block font-semibold text-white">Bedrooms</label>
              <select id={ids.beds} value={answers.bedrooms ?? ""} className={field}
                onChange={(e) => update({ bedrooms: Number(e.target.value) })}>
                <option value="" disabled>Choose</option>
                {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n === 5 ? "5 or more" : n}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor={ids.people} className="mb-1 block font-semibold text-white">People living there</label>
              <select id={ids.people} value={answers.people ?? ""} className={field}
                onChange={(e) => update({ people: Number(e.target.value) })}>
                <option value="" disabled>Choose</option>
                {[1, 2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n === 6 ? "6 or more" : n}</option>)}
              </select>
            </div>
          </div>

          <Choice<Heating>
            name="heat" legend="How is it heated?" value={answers.heating}
            hint="Homes heated by electricity (storage heaters, electric radiators or a heat pump) use far more in winter."
            options={[{ value: "gas", label: "Gas, oil or another fuel" }, { value: "electric", label: "Electricity" }]}
            onChange={(v) => update({ heating: v })}
          />

          {hasEv && (
            <div className="mb-6 sm:w-64">
              <label htmlFor={ids.miles} className="mb-1 block font-semibold text-white">Miles driven a year (electric car)</label>
              <input id={ids.miles} type="number" inputMode="numeric" min={0} max={60000} step={500}
                value={answers.evMiles ?? ""} placeholder="7000" className={field}
                onChange={(e) => save({ ...answers, evMiles: e.target.value === "" ? null : Math.round(Number(e.target.value)) })}
              />
              <p className="mt-1 text-sm text-slate-400">The UK average is about 7,000.</p>
            </div>
          )}

          <div className="mb-2 rounded-xl border border-slate-700 bg-[#0f1f38] p-5">
            {/* Plain-text label: a <Term> button inside a <label> would be invalid and blank the field's name. */}
            <label htmlFor={ids.kwh} className="mb-1 block font-semibold text-white">
              Electricity used a year (kWh)
            </label>
            <p className="mb-3 text-sm text-slate-300">
              {kwhTyped
                ? "Using your figure."
                : "Our estimate for a home like yours. If a bill or your supplier's app shows your yearly use, enter that instead: it's more accurate."}{" "}
              Measured in <Term k="kwh">kilowatt-hours</Term>.
            </p>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <input id={ids.kwh} type="number" inputMode="numeric" min={500} max={20000} step={100}
                value={answers.annualKwh ?? ""} className={`${field} sm:w-48`}
                onChange={(e) => {
                  setKwhTyped(true);
                  const n = Math.round(Number(e.target.value));
                  save({ ...answers, annualKwh: e.target.value === "" || n < 500 || n > 20000 ? null : n });
                }}
              />
              {kwhTyped && answers.propertyType && answers.bedrooms && (
                <button type="button" className="text-sm text-slate-300 underline underline-offset-4 hover:text-white"
                  onClick={() => { setKwhTyped(false); save({ ...answers, annualKwh: suggestKwh(answers.propertyType!, answers.bedrooms!, answers.people, answers.heating === "electric" ? epcKwh : null) }); }}>
                  Use our estimate instead
                </button>
              )}
            </div>
            <p className="mt-2 text-sm text-slate-400">Between 500 and 20,000 kWh. A typical home uses about 2,700.</p>
          </div>
        </section>
      )}

      <div className="mt-8 flex flex-col items-end gap-2">
        <button type="button" className={`${primary} px-8 text-lg`} disabled={!complete}
          onClick={() => router.push(stepHref("/check/confirm", query))}>
          Continue
        </button>
        {!complete && showDetails && <p className="text-sm text-slate-400">Choose the type of home and its yearly use to continue.</p>}
      </div>
    </>
  );
}
