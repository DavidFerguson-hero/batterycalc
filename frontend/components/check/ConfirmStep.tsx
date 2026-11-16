"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useId, useMemo, useState } from "react";

import Term from "@/components/Term";
import { type TariffSummary, fetchTariffs } from "@/lib/api";
import { PROPERTY_LABELS, parseEstimate } from "@/lib/estimate";
import { HOME_ITEMS, type HomeItem, ROUTE_PATHS, hasNothing, parseJourney, stepHref } from "@/lib/journey";
import { type Missing, buildAssessRequest } from "@/lib/request";
import {
  TYPICAL_RATE_P, TYPICAL_STANDING_P, type TariffAnswers, isTimeOfUse, parseTariff, writeTariff,
} from "@/lib/tariff";
import { useUploads } from "@/lib/uploads";

const field = "w-full rounded-lg border border-slate-500 bg-[#0a1628] px-3 py-3 text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white";
const link = "text-sm text-slate-200 underline underline-offset-4 hover:text-white";

const HOME_NAMES: Record<HomeItem, string> = { solar: "Solar panels", heat_pump: "Heat pump", ev: "Electric car", battery: "Home battery" };
const OWN: Record<string, string> = { have: "have", planning: "planning" };
const MISSING_TEXT: Record<Missing, string> = {
  route: "how you'd like to tell us your usage",
  usage_kwh: "your yearly electricity use",
  property_type: "the type of home",
  files: "your usage file",
  tariff: "which time-of-use tariff you're on",
};

function Row({ label, children, href, query }: { label: string; children: React.ReactNode; href: string; query: string }) {
  return (
    <div className="flex flex-col gap-1 border-b border-slate-700 py-4 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
      <dt className="font-semibold text-white sm:w-40 sm:shrink-0">{label}</dt>
      <dd className="flex-1 text-slate-200">{children}</dd>
      <dd className="sm:text-right">
        <Link href={stepHref(href, query)} className={link}>
          Change<span className="sr-only"> {label.toLowerCase()}</span>
        </Link>
      </dd>
    </div>
  );
}

function RadioCard({ id, name, checked, onChange, children }: {
  id: string; name: string; checked: boolean; onChange: () => void; children: React.ReactNode;
}) {
  return (
    <div>
      <input type="radio" id={id} name={name} checked={checked} onChange={onChange} className="peer sr-only" />
      <label
        htmlFor={id}
        className={`flex min-h-12 cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-white ${
          checked ? "border-[#f97316] bg-[#f97316]/10 font-semibold text-white" : "border-slate-600 text-slate-100 hover:border-slate-400"
        }`}
      >
        <span aria-hidden="true" className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 ${checked ? "border-[#f97316]" : "border-slate-400"}`}>
          {checked && <span className="h-2.5 w-2.5 rounded-full bg-[#f97316]" />}
        </span>
        <span>{children}</span>
      </label>
    </div>
  );
}

export default function ConfirmStep() {
  const router = useRouter();
  const pathname = usePathname();
  const query = useSearchParams().toString();
  const journey = parseJourney(query);
  const est = parseEstimate(query);
  const tariff = parseTariff(query);
  const { files, check } = useUploads();
  const hasFiles = files.length > 0 && !!check?.combined;
  const built = buildAssessRequest(query, hasFiles);

  const [tariffs, setTariffs] = useState<TariffSummary[] | null>(null);
  const [tariffsFailed, setTariffsFailed] = useState(false);
  const [search, setSearch] = useState("");
  const ids = { rate: useId(), sc: useId(), exp: useId(), search: useId() };

  useEffect(() => {
    const ctrl = new AbortController();
    fetchTariffs(ctrl.signal).then(setTariffs).catch(() => { if (!ctrl.signal.aborted) setTariffsFailed(true); });
    return () => ctrl.abort();
  }, []);

  const timeOfUse = useMemo(() => (tariffs ?? []).filter((t) => !t.is_flat_rate), [tariffs]);
  const shown = useMemo(() => {
    const s = search.trim().toLowerCase();
    return s ? timeOfUse.filter((t) => `${t.name} ${t.supplier}`.toLowerCase().includes(s)) : timeOfUse;
  }, [timeOfUse, search]);
  const chosenTou = timeOfUse.find((t) => t.key === tariff.choice);

  function saveTariff(next: TariffAnswers) {
    router.replace(stepHref(pathname, writeTariff(next, query)), { scroll: false });
  }
  const setNum = (key: "unitRateP" | "standingP" | "exportP", v: string) => {
    const n = v === "" ? null : Math.round(Number(v) * 100) / 100;
    saveTariff({ ...tariff, [key]: n === null || Number.isNaN(n) ? null : n });
  };

  const inferredRate = journey.route === "upload" ? check?.combined?.inferred_unit_rate_p ?? null : null;
  const hasSolar = journey.home.solar !== "none";
  const mode: "flat" | "tou" | "unsure" =
    tariff.choice === "flat" ? "flat" : tariff.choice === "tou" || isTimeOfUse(tariff.choice) ? "tou" : "unsure";

  // ── Summary text ─────────────────────────────────────────────────────────
  const homeText = hasNothing(journey.home)
    ? "None of solar panels, a heat pump, an electric car or a home battery"
    : HOME_ITEMS.filter((i) => journey.home[i] !== "none").map((i) => `${HOME_NAMES[i]}: ${OWN[journey.home[i]]}`).join(" · ");

  let usage: React.ReactNode;
  let usageHref = "/check/usage";
  if (journey.route === "upload") {
    usageHref = ROUTE_PATHS.upload;
    usage = hasFiles && check?.combined ? (
      <>Your smart meter data: {check.combined.days_found} days, about{" "}
        <strong className="text-white">{Math.round(check.combined.annual_kwh_estimate).toLocaleString("en-GB")} kWh a year</strong>.</>
    ) : (
      <span className="text-[#fdba74]">
        Your usage file isn&apos;t loaded any more (we don&apos;t keep files once the page is closed or reloaded). Please add it again.
      </span>
    );
  } else if (journey.route === "estimate") {
    usageHref = ROUTE_PATHS.estimate;
    const bits = [
      est.propertyType ? PROPERTY_LABELS[est.propertyType] : null,
      est.bedrooms ? `${est.bedrooms}${est.bedrooms === 5 ? "+" : ""} bedroom${est.bedrooms === 1 ? "" : "s"}` : null,
      est.people ? `${est.people}${est.people === 6 ? "+" : ""} ${est.people === 1 ? "person" : "people"}` : null,
      est.heating === "electric" ? "electric heating" : "gas or other heating",
      est.epcRating ? `EPC ${est.epcRating}` : null,
    ].filter(Boolean);
    usage = (
      <>Quick estimate: {bits.join(", ")}.{" "}
        {est.annualKwh ? <>About <strong className="text-white">{est.annualKwh.toLocaleString("en-GB")} kWh a year</strong>.</> : <span className="text-[#fdba74]">Yearly use not set.</span>}
        {journey.home.ev !== "none" && <> Electric car: {(est.evMiles ?? 7000).toLocaleString("en-GB")} miles a year{est.evMiles === null ? " (typical)" : ""}.</>}
      </>
    );
  } else {
    usage = <span className="text-[#fdba74]">Not chosen yet.</span>;
  }

  return (
    <>
      {/* ── Summary ──────────────────────────────────────────────── */}
      <section aria-labelledby="summary-heading">
        <h2 id="summary-heading" className="mb-2 text-xl font-semibold">Your answers</h2>
        <dl className="border-t border-slate-700">
          <Row label="Your home" href="/check" query={query}>{homeText}</Row>
          <Row label="Your usage" href={usageHref} query={query}>{usage}</Row>
        </dl>
      </section>

      {/* ── Tariff ───────────────────────────────────────────────── */}
      <section aria-labelledby="tariff-heading" className="mt-10">
        <h2 id="tariff-heading" className="mb-1 text-xl font-semibold">Your current tariff</h2>
        <p className="mb-4 text-sm text-slate-300">
          We compare your current <Term k="tariff" /> with the best ones for your home, with and without a battery.
          Your latest bill shows your rates, and whether you&apos;re on a <Term k="time_of_use" />.
        </p>

        <fieldset className="mb-4">
          <legend className="sr-only">What kind of tariff are you on?</legend>
          <div className="grid gap-2 sm:grid-cols-3">
            <RadioCard id="tariff-flat" name="tariff-kind" checked={mode === "flat"}
              onChange={() => saveTariff({ ...tariff, choice: "flat", unitRateP: tariff.unitRateP ?? inferredRate ?? null })}>
              A standard tariff (one price all day)
            </RadioCard>
            <RadioCard id="tariff-tou" name="tariff-kind" checked={mode === "tou"}
              onChange={() => saveTariff({ ...tariff, choice: "tou" })}>
              A time-of-use tariff (cheaper at certain times)
            </RadioCard>
            <RadioCard id="tariff-unsure" name="tariff-kind" checked={mode === "unsure"}
              onChange={() => saveTariff({ ...tariff, choice: "unsure" })}>
              I&apos;m not sure
            </RadioCard>
          </div>
        </fieldset>

        <div aria-live="polite">
          {mode === "flat" && (
            <div className="grid gap-4 rounded-xl border border-slate-700 bg-[#0f1f38] p-5 sm:grid-cols-2">
              <div>
                <label htmlFor={ids.rate} className="mb-1 block font-semibold text-white">Unit rate (pence per kWh)</label>
                <input id={ids.rate} type="number" inputMode="decimal" step="0.01" min={5} max={100}
                  placeholder={String(TYPICAL_RATE_P)} value={tariff.unitRateP ?? ""} className={field}
                  onChange={(e) => setNum("unitRateP", e.target.value)} />
                {inferredRate !== null && tariff.unitRateP !== inferredRate && (
                  <button type="button" className={`${link} mt-2`} onClick={() => saveTariff({ ...tariff, unitRateP: inferredRate })}>
                    Use {inferredRate}p, worked out from your file
                  </button>
                )}
              </div>
              <div>
                <label htmlFor={ids.sc} className="mb-1 block font-semibold text-white">
                  Standing charge (pence per day)
                </label>
                <input id={ids.sc} type="number" inputMode="decimal" step="0.01" min={0} max={200}
                  placeholder={String(TYPICAL_STANDING_P)} value={tariff.standingP ?? ""} className={field}
                  onChange={(e) => setNum("standingP", e.target.value)} />
              </div>
              <p className="text-sm text-slate-300 sm:col-span-2">
                Leave either blank to use a typical figure ({TYPICAL_RATE_P}p per kWh and {TYPICAL_STANDING_P}p a day).
                The <Term k="standing_charge" /> is the fixed daily amount.
              </p>
            </div>
          )}

          {mode === "tou" && (
            <div className="rounded-xl border border-slate-700 bg-[#0f1f38] p-5">
              <label htmlFor={ids.search} className="mb-1 block font-semibold text-white">Find your tariff</label>
              <input id={ids.search} type="search" value={search} onChange={(e) => setSearch(e.target.value)}
                placeholder="e.g. Octopus Go, Economy 7" className={`${field} mb-3`} autoComplete="off" />
              {tariffsFailed && <p className="text-[#fdba74]">We couldn&apos;t load the list of tariffs. Please try again, or choose a standard tariff.</p>}
              {!tariffs && !tariffsFailed && <p className="text-slate-300">Loading tariffs…</p>}
              {tariffs && (
                <fieldset>
                  <legend className="sr-only">Your time-of-use tariff</legend>
                  <p className="sr-only" aria-live="polite">{shown.length} {shown.length === 1 ? "tariff" : "tariffs"} shown</p>
                  <div className="grid max-h-80 gap-2 overflow-y-auto pr-1">
                    {shown.map((t) => (
                      <RadioCard key={t.key} id={`tariff-${t.key}`} name="tariff-key" checked={tariff.choice === t.key}
                        onChange={() => saveTariff({ ...tariff, choice: t.key })}>
                        {t.name} <span className="font-normal text-slate-300">· {t.supplier}</span>
                      </RadioCard>
                    ))}
                    {shown.length === 0 && <p className="text-slate-300">No tariffs match “{search}”.</p>}
                  </div>
                  <p className="mt-3 text-sm text-slate-300">
                    Can&apos;t see yours? Choose “A standard tariff” and enter your rates, or “I&apos;m not sure”.
                  </p>
                  {chosenTou && <p className="mt-2 text-sm text-slate-300">{chosenTou.description}</p>}
                </fieldset>
              )}
            </div>
          )}

          {mode === "unsure" && (
            <p className="rounded-xl border border-slate-700 bg-[#0f1f38] p-5 text-slate-300">
              We&apos;ll use typical rates for a standard tariff: {TYPICAL_RATE_P}p per kWh and {TYPICAL_STANDING_P}p a day.
            </p>
          )}
        </div>

        {hasSolar && (
          <div className="mt-6 sm:w-72">
            <label htmlFor={ids.exp} className="mb-1 block font-semibold text-white">Export rate (pence per kWh)</label>
            <input id={ids.exp} type="number" inputMode="decimal" step="0.01" min={0} max={100}
              placeholder="e.g. 15" value={tariff.exportP ?? ""} className={field}
              onChange={(e) => setNum("exportP", e.target.value)} />
            <p className="mt-1 text-sm text-slate-300">
              What you&apos;re paid for electricity you <Term k="export" />. Leave blank if you&apos;re not sure.
            </p>
          </div>
        )}
      </section>

      {/* ── Continue ─────────────────────────────────────────────── */}
      <div className="mt-10 flex flex-col items-end gap-2">
        <button
          type="button"
          disabled={!built.request}
          onClick={() => router.push(stepHref("/check/results", query))}
          className="rounded-full bg-[#f97316] px-8 py-3 text-lg font-semibold text-[#0a1628] transition-colors hover:bg-[#fb8a3c] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-200"
        >
          See my answer
        </button>
        {!built.request && (
          <p className="text-right text-sm text-slate-300">
            We still need {built.missing.map((m) => MISSING_TEXT[m]).join(" and ")}.
          </p>
        )}
      </div>
    </>
  );
}
