"use client";

import { useEffect, useId, useState } from "react";

import { ApiError, type AssessRequest, type AssessResponse, assess } from "@/lib/api";
import { VERDICT, gbp, years } from "@/lib/format";
import { type LoadStatus, PRICE_MAX, PRICE_MIN, type WhatIf, applyWhatIf, initialWhatIf, sameWhatIf } from "@/lib/whatif";

const DEBOUNCE_MS = 700;

type Result =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "done"; data: AssessResponse }
  | { kind: "error"; message: string };

interface Props {
  data: AssessResponse;
  base: AssessRequest;
  files: File[];
  ev: LoadStatus;
  heatPump: LoadStatus;
}

/** "What would make it pay back?" (H14) and live what-ifs (H6), re-run through the API as you change them. */
export default function WhatIfs({ data, base, files, ev, heatPump }: Props) {
  const start = initialWhatIf(data.recommendation, ev, heatPump);
  const [w, setW] = useState<WhatIf>(start);
  const [priceEdited, setPriceEdited] = useState(false);
  const [priceText, setPriceText] = useState(String(start.priceGbp));
  const [result, setResult] = useState<Result>({ kind: "idle" });
  const changed = !sameWhatIf(w, start);
  const ids = { size: useId(), price: useId(), priceHint: useId() };
  const life = data.assumptions.battery_life_years;
  const sizes = data.size_comparison.all_sizes;
  const levers = data.what_would_make_it_pay_back;

  // Debounced live recalculation: wait for a pause in typing, cancel any older request.
  useEffect(() => {
    if (!changed) return;
    const ctrl = new AbortController();
    const timer = setTimeout(() => {
      setResult({ kind: "loading" });
      assess(applyWhatIf(base, w), base.usage.route === "upload" ? files : [], ctrl.signal)
        .then((d) => setResult({ kind: "done", data: d }))
        .catch((e) => {
          if (!ctrl.signal.aborted) {
            setResult({ kind: "error", message: e instanceof ApiError ? e.message : "Couldn't work that out. Please try again." });
          }
        });
    }, DEBOUNCE_MS);
    return () => { clearTimeout(timer); ctrl.abort(); };
    // w and changed are the inputs; base and files are fixed for this answer.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [w.sizeKwh, w.priceGbp, w.ev, w.heatPump]);

  const typicalFor = (kwh: number) => sizes.find((r) => r.kwh === kwh)?.installed_cost ?? w.priceGbp;

  const setSize = (kwh: number) => {
    // Until they type a price, follow the typical price for the size they pick.
    const price = priceEdited ? w.priceGbp : typicalFor(kwh);
    if (!priceEdited) setPriceText(String(price));
    setW({ ...w, sizeKwh: kwh, priceGbp: price });
  };
  const setPrice = (text: string) => {
    setPriceText(text);
    setPriceEdited(true);
    const n = Number(text.replace(/[£,\s]/g, ""));
    if (Number.isFinite(n) && n >= PRICE_MIN && n <= PRICE_MAX) setW((p) => ({ ...p, priceGbp: n }));
  };
  const tryPrice = (n: number) => { setPriceText(String(n)); setPriceEdited(true); setW((p) => ({ ...p, priceGbp: n })); };
  const reset = () => { setW(start); setPriceText(String(start.priceGbp)); setPriceEdited(false); setResult({ kind: "idle" }); };

  const priceNum = Number(priceText.replace(/[£,\s]/g, ""));
  const priceInvalid = !Number.isFinite(priceNum) || priceNum < PRICE_MIN || priceNum > PRICE_MAX;

  return (
    <section aria-labelledby="whatif-heading">
      <h2 id="whatif-heading" className="mb-1 text-xl font-semibold">What if…?</h2>
      <p className="mb-4 text-sm text-slate-300">Change any of these and we&apos;ll work out the answer again.</p>

      {levers && (
        <div className="mb-5 rounded-xl border border-slate-700 bg-[#0f1f38] p-4 text-slate-200">
          <h3 className="mb-2 font-semibold text-white">What would make it pay back</h3>
          <ul className="list-disc space-y-1.5 pl-5">
            {levers.price.price_for_payback_within_warranty !== null && (
              <li>
                A fitted price of <strong className="text-white">{gbp(levers.price.price_for_payback_within_warranty)}</strong> or
                less would pay back within the {data.assumptions.warranty_years}-year warranty
                {levers.price.price_for_worth_it !== null && <>, and {gbp(levers.price.price_for_worth_it)} or less would make it worth it</>}.{" "}
                <button type="button" onClick={() => tryPrice(levers.price.price_for_payback_within_warranty!)}
                  className="text-white underline underline-offset-4">Try {gbp(levers.price.price_for_payback_within_warranty)}</button>
              </li>
            )}
            {levers.switch_tariff && (
              <li>
                On {levers.switch_tariff.tariff_name} it would pay back in {years(levers.switch_tariff.payback_years, life)}
                {levers.switch_tariff.changes_verdict ? ` (${VERDICT[levers.switch_tariff.verdict].title.toLowerCase()})` : ", which doesn't change the answer"}.
              </li>
            )}
            {levers.add_ev && (
              <li>
                With an electric car ({Math.round(levers.add_ev.annual_miles ?? 0).toLocaleString("en-GB")} miles a year) it would
                pay back in {years(levers.add_ev.payback_years, life)}
                {levers.add_ev.changes_verdict ? ` (${VERDICT[levers.add_ev.verdict].title.toLowerCase()})` : ", which doesn't change the answer"}.
              </li>
            )}
          </ul>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor={ids.size} className="mb-1 block text-sm text-slate-200">Battery size</label>
          <select id={ids.size} value={w.sizeKwh} onChange={(e) => setSize(Number(e.target.value))}
            className="w-full rounded-lg border border-slate-500 bg-[#0a1628] px-3 py-2 text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-white">
            {sizes.map((r) => <option key={r.kwh} value={r.kwh}>{r.label} (typically {gbp(r.installed_cost)})</option>)}
          </select>
        </div>
        <div>
          <label htmlFor={ids.price} className="mb-1 block text-sm text-slate-200">Fitted price, £</label>
          <input id={ids.price} inputMode="numeric" value={priceText} onChange={(e) => setPrice(e.target.value)}
            aria-describedby={ids.priceHint} aria-invalid={priceInvalid}
            className="w-full rounded-lg border border-slate-500 bg-[#0a1628] px-3 py-2 text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-white" />
          <p id={ids.priceHint} className={`mt-1 text-sm ${priceInvalid ? "text-[#fca5a5]" : "text-slate-400"}`}>
            {priceInvalid ? `Enter a price between ${gbp(PRICE_MIN)} and ${gbp(PRICE_MAX)}.` : "Use a quote you've had, or try a lower price."}
          </p>
        </div>
      </div>

      <fieldset className="mt-4">
        <legend className="mb-2 text-sm text-slate-200">Things you might add</legend>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {ev !== "have" && (
            <label className="flex items-center gap-2 text-slate-100">
              <input type="checkbox" checked={w.ev} onChange={(e) => setW((p) => ({ ...p, ev: e.target.checked }))}
                className="h-5 w-5 accent-[#f97316]" />
              An electric car
            </label>
          )}
          {heatPump !== "have" && (
            <label className="flex items-center gap-2 text-slate-100">
              <input type="checkbox" checked={w.heatPump} onChange={(e) => setW((p) => ({ ...p, heatPump: e.target.checked }))}
                className="h-5 w-5 accent-[#f97316]" />
              A heat pump
            </label>
          )}
        </div>
        {(ev === "have" || heatPump === "have") && (
          <p className="mt-2 text-sm text-slate-400">
            Your {ev === "have" && heatPump === "have" ? "electric car and heat pump are" : ev === "have" ? "electric car is" : "heat pump is"} already included.
          </p>
        )}
      </fieldset>

      <div aria-live="polite" className="mt-5">
        {changed && <WhatIfResult result={result} before={data} life={life} />}
      </div>
      {changed && (
        <button type="button" onClick={reset} className="mt-3 text-sm text-slate-200 underline underline-offset-4 hover:text-white">
          Back to your answer
        </button>
      )}
    </section>
  );
}

function WhatIfResult({ result, before, life }: { result: Result; before: AssessResponse; life: number }) {
  if (result.kind === "idle" || result.kind === "loading") {
    return <p className="rounded-xl border border-slate-700 p-4 text-slate-300">Working it out…</p>;
  }
  if (result.kind === "error") {
    return <p className="rounded-xl border border-[#fca5a5] bg-[#fca5a5]/10 p-4 text-slate-100">{result.message}</p>;
  }
  const after = result.data;
  const rows: [string, string, string][] = [
    ["Verdict", VERDICT[before.verdict].title, VERDICT[after.verdict].title],
    ["Battery", `${before.recommendation.battery_label} on ${before.recommendation.tariff_name}`,
      `${after.recommendation.battery_label} on ${after.recommendation.tariff_name}`],
    ["Cost fitted", gbp(before.recommendation.installed_price), gbp(after.recommendation.installed_price)],
    ["First-year saving", gbp(before.headline.year1_battery_saving), gbp(after.headline.year1_battery_saving)],
    ["Pays back in", years(before.headline.payback_years.likely, life), years(after.headline.payback_years.likely, life)],
    [`Ahead after ${life} years`, gbp(before.headline.lifetime_net_gain.likely), gbp(after.headline.lifetime_net_gain.likely)],
  ];
  return (
    <div className={`rounded-xl border-2 p-4 ${VERDICT[after.verdict].tone}`}>
      <p className="mb-3 text-lg text-white">
        With these changes: <strong><span aria-hidden="true">{VERDICT[after.verdict].icon} </span>{VERDICT[after.verdict].title}</strong>
      </p>
      <table className="w-full text-left text-sm">
        <caption className="sr-only">Your answer compared with these changes</caption>
        <thead className="text-slate-300">
          <tr>
            <td />
            <th scope="col" className="py-1 pr-3 font-normal">Your answer</th>
            <th scope="col" className="py-1 font-normal">With these changes</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([k, a, b]) => (
            <tr key={k} className="border-t border-slate-700/60">
              <th scope="row" className="py-1.5 pr-3 font-normal text-slate-300">{k}</th>
              <td className="py-1.5 pr-3 text-slate-200">{a}</td>
              <td className={`py-1.5 font-semibold ${a === b ? "text-slate-200" : "text-white"}`}>{b}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
