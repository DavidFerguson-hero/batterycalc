"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import Term from "@/components/Term";
import { ROUTE_PATHS, type Route, parseJourney, stepHref, withRoute } from "@/lib/journey";

const CARDS: Record<Route, {
  title: string;
  time: string;
  accuracy: string;
  body: React.ReactNode;
  need: React.ReactNode[];
}> = {
  upload: {
    title: "I have my usage data",
    time: "About 10 minutes",
    accuracy: "Most accurate",
    body: (
      <>
        Download your smart meter&apos;s <Term k="half_hourly" /> from your supplier&apos;s website or app and
        upload it here. We&apos;ll show you how for your supplier.
      </>
    ),
    need: [
      "A smart meter",
      "Your energy supplier's online account login",
      "Ideally a full year of readings (a few months works too)",
    ],
  },
  estimate: {
    title: "Quick estimate",
    time: "About 2 minutes",
    accuracy: "A good first answer",
    body: (
      <>
        We estimate your use from your home&apos;s <Term k="epc" /> and a couple of questions, using typical
        patterns for homes like yours.
      </>
    ),
    need: ["Your postcode", "How many people live there"],
  },
};

export default function RouteChoice() {
  const query = useSearchParams().toString();
  const current = parseJourney(query).route;

  return (
    <>
      <ul className="grid gap-4 sm:grid-cols-2">
        {(Object.keys(CARDS) as Route[]).map((route) => {
          const c = CARDS[route];
          const headingId = `route-${route}`;
          const chosen = current === route;
          return (
            <li key={route} className="flex">
              {/* "Stretched link": the heading's link covers the whole card, while the term
                  buttons sit above it, so there's no button nested inside a link. */}
              <div
                className={`relative flex w-full flex-col rounded-xl border p-5 transition-colors hover:border-[#f97316] has-[a:focus-visible]:outline has-[a:focus-visible]:outline-2 has-[a:focus-visible]:outline-offset-4 has-[a:focus-visible]:outline-white ${
                  chosen ? "border-[#f97316] bg-[#f97316]/10" : "border-slate-700 bg-[#0f1f38]"
                }`}
              >
                <h2 id={headingId} className="mb-1 text-xl font-semibold text-white">
                  <Link
                    href={stepHref(ROUTE_PATHS[route], withRoute(route, query))}
                    aria-describedby={`${headingId}-meta`}
                    className="outline-none after:absolute after:inset-0 after:rounded-xl after:content-['']"
                  >
                    {c.title}
                  </Link>
                  {chosen && <span className="ml-2 text-sm font-normal text-slate-300">(your last choice)</span>}
                </h2>
                <p id={`${headingId}-meta`} className="mb-3 text-sm font-medium text-[#fdba74]">
                  {c.time} <span aria-hidden="true">·</span> {c.accuracy}
                </p>
                <p className="relative z-10 mb-4 leading-relaxed text-slate-300">{c.body}</p>
                <p className="mb-2 text-sm font-semibold text-white">You&apos;ll need:</p>
                <ul className="mb-5 list-disc space-y-1 pl-5 text-sm text-slate-300">
                  {c.need.map((n, i) => <li key={i}>{n}</li>)}
                </ul>
                <span aria-hidden="true" className="mt-auto inline-flex items-center gap-2 font-semibold text-white">
                  {route === "upload" ? "Use my data" : "Get a quick estimate"} →
                </span>
              </div>
            </li>
          );
        })}
      </ul>

      <p className="mt-6 text-sm leading-relaxed text-slate-300">
        Not sure? Start with the quick estimate. You can add your real data afterwards to firm up the answer.
      </p>

      <p className="mt-8">
        <Link
          href={stepHref("/check", query)}
          className="text-slate-300 underline-offset-4 hover:text-white hover:underline"
        >
          <span aria-hidden="true">←</span> Back to your home
        </Link>
      </p>
    </>
  );
}
