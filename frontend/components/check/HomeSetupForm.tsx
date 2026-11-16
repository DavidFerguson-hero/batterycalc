"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import Term from "@/components/Term";
import {
  HOME_ITEMS, type HomeItem, type Ownership, hasNothing, parseJourney, stepHref, writeJourney,
} from "@/lib/journey";

const ITEMS: Record<HomeItem, {
  title: string;
  why: React.ReactNode;
  options: { value: Ownership; label: string }[];
}> = {
  solar: {
    title: "Solar panels",
    why: <>A battery can store solar you&apos;d otherwise <Term k="export">export</Term> for less.</>,
    options: [
      { value: "none", label: "No" },
      { value: "have", label: "Have them" },
      { value: "planning", label: "Planning to get them" },
    ],
  },
  heat_pump: {
    title: "Heat pump",
    why: <>Heat pumps use most of their electricity in winter, which changes the best battery size.</>,
    options: [
      { value: "none", label: "No" },
      { value: "have", label: "Have one" },
      { value: "planning", label: "Planning to get one" },
    ],
  },
  ev: {
    title: "Electric car",
    why: <>Charging overnight on a cheap <Term k="tariff" /> can save more than a battery does.</>,
    options: [
      { value: "none", label: "No" },
      { value: "have", label: "Have one" },
      { value: "planning", label: "Planning to get one" },
    ],
  },
  battery: {
    title: "Home battery",
    why: <>Tell us if you already have one.</>,
    options: [
      { value: "none", label: "No" },
      { value: "have", label: "Already have one" },
    ],
  },
};

export default function HomeSetupForm() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const query = params.toString();
  const journey = parseJourney(params);

  function choose(item: HomeItem, value: Ownership) {
    const next = { ...journey, home: { ...journey.home, [item]: value } };
    router.replace(stepHref(pathname, writeJourney(next, query)), { scroll: false });
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        router.push(stepHref("/check/usage", query));
      }}
    >
      <div className="space-y-6">
        {HOME_ITEMS.map((item) => {
          const cfg = ITEMS[item];
          const hintId = `hint-${item}`;
          return (
            <fieldset key={item} aria-describedby={hintId} className="rounded-xl border border-slate-700 bg-[#0f1f38] p-4 sm:p-5">
              <legend className="px-1 text-lg font-semibold">{cfg.title}</legend>
              <p id={hintId} className="mb-3 text-sm leading-relaxed text-slate-300">{cfg.why}</p>
              <div className={`grid gap-2 ${cfg.options.length === 3 ? "sm:grid-cols-3" : "sm:grid-cols-2"}`}>
                {cfg.options.map((o) => {
                  const id = `${item}-${o.value}`;
                  const checked = journey.home[item] === o.value;
                  return (
                    <div key={o.value}>
                      <input
                        type="radio"
                        id={id}
                        name={item}
                        value={o.value}
                        checked={checked}
                        onChange={() => choose(item, o.value)}
                        className="peer sr-only"
                      />
                      <label
                        htmlFor={id}
                        className={`flex min-h-12 cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 transition-colors peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-white ${
                          checked
                            ? "border-[#f97316] bg-[#f97316]/10 font-semibold text-white"
                            : "border-slate-600 text-slate-100 hover:border-slate-400"
                        }`}
                      >
                        {/* Selected is shown by the filled dot and bold text, not by colour alone. */}
                        <span
                          aria-hidden="true"
                          className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 ${
                            checked ? "border-[#f97316]" : "border-slate-400"
                          }`}
                        >
                          {checked && <span className="h-2.5 w-2.5 rounded-full bg-[#f97316]" />}
                        </span>
                        <span>{o.label}</span>
                      </label>
                    </div>
                  );
                })}
              </div>
            </fieldset>
          );
        })}
      </div>

      <p className="mt-6 text-sm text-slate-300" aria-live="polite">
        {hasNothing(journey.home)
          ? "None of these yet? That's fine: most people start here."
          : "Thanks. We'll include these in your answer."}
      </p>

      <div className="mt-6 flex flex-col-reverse items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Link href="/" className="text-center text-slate-300 underline-offset-4 hover:text-white hover:underline">
          Back to home page
        </Link>
        <button
          type="submit"
          className="rounded-full bg-[#f97316] px-8 py-3 text-lg font-semibold text-[#0a1628] transition-colors hover:bg-[#fb8a3c] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white"
        >
          Continue
        </button>
      </div>
    </form>
  );
}
