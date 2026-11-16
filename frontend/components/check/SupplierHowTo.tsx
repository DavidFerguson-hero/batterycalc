"use client";

import { useId, useState } from "react";

/**
 * How to get half-hourly usage data, by supplier.
 *
 * Checked against suppliers' help pages and customer forums in November 2026. Suppliers
 * change their websites often, so the steps stay general where we couldn't confirm the
 * exact button names, and the Bright app is offered to everyone as the route that works
 * with any supplier.
 */
const SUPPLIERS = {
  octopus: {
    name: "Octopus Energy",
    steps: [
      "Log in to your Octopus Energy account on their website.",
      "Open your electricity usage and look for the option to download your readings as a CSV file.",
      "If you only see daily figures, set your smart meter to send half-hourly readings in your account settings, then try again in a day or two.",
    ],
  },
  ovo: {
    name: "OVO",
    steps: [
      "Open the OVO app or log in to MyOVO.",
      "Go to Usage, choose “View as table” under the graph, then “Download data”.",
      "OVO may only let you download a limited period at a time. Download several and add them all here.",
    ],
  },
  british_gas: {
    name: "British Gas",
    steps: [
      "British Gas doesn't currently offer a half-hourly download in its online account.",
      "The quickest way is the free Bright app (below), which works with any supplier.",
      "You can also ask British Gas's webchat team for your past smart meter data.",
    ],
  },
  edf: {
    name: "EDF",
    steps: [
      "In your EDF online account you can set your smart meter to record half-hourly readings (“Smart meter preferences”).",
      "EDF doesn't currently offer home customers a download of those readings.",
      "Use the free Bright app (below) to download them.",
    ],
  },
  eon: {
    name: "E.ON Next",
    steps: [
      "The E.ON Next app shows your usage but doesn't currently let you download it.",
      "Use the free Bright app (below), or ask E.ON Next to email you up to 12 months of readings. This is free: ask for a “subject access request”.",
    ],
  },
  other: {
    name: "Another supplier",
    steps: [
      "Look in your supplier's online account or app for a way to download your usage, ideally half-hourly, as a CSV file.",
      "If there isn't one, use the free Bright app (below).",
    ],
  },
} as const;

type SupplierKey = keyof typeof SUPPLIERS;

export default function SupplierHowTo() {
  const [supplier, setSupplier] = useState<SupplierKey | "">("");
  const selectId = useId();

  return (
    <section aria-labelledby="howto-heading" className="rounded-xl border border-slate-700 bg-[#0f1f38] p-5">
      <h2 id="howto-heading" className="mb-3 text-xl font-semibold">How to get your data</h2>

      <label htmlFor={selectId} className="mb-2 block text-slate-200">Who supplies your electricity?</label>
      <select
        id={selectId}
        value={supplier}
        onChange={(e) => setSupplier(e.target.value as SupplierKey | "")}
        className="mb-4 w-full rounded-lg border border-slate-500 bg-[#0a1628] px-3 py-3 text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white sm:w-80"
      >
        <option value="">Choose your supplier</option>
        {(Object.keys(SUPPLIERS) as SupplierKey[]).map((k) => (
          <option key={k} value={k}>{SUPPLIERS[k].name}</option>
        ))}
      </select>

      <div aria-live="polite">
        {supplier && (
          <ol className="mb-5 list-decimal space-y-2 pl-5 leading-relaxed text-slate-300">
            {SUPPLIERS[supplier].steps.map((s, i) => <li key={i}>{s}</li>)}
          </ol>
        )}
      </div>

      <div className="rounded-lg border border-slate-700 p-4">
        <h3 className="mb-2 font-semibold text-white">Any supplier: the free Bright app</h3>
        <ol className="list-decimal space-y-2 pl-5 text-sm leading-relaxed text-slate-300">
          <li>
            Install <strong className="text-white">Bright</strong> (by Hildebrand, a company licensed to read smart
            meter data with your permission) and follow its steps to connect your meter.
          </li>
          <li>
            Log in at <span className="text-white">glowmarkt.com</span> with the same account and download your
            electricity readings as a CSV file. It can usually fetch up to 12 months of history.
          </li>
        </ol>
        <p className="mt-2 text-sm text-slate-400">Works with most smart meters. It can take a day or two to connect.</p>
      </div>
    </section>
  );
}
